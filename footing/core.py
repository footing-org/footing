import collections
import contextlib
import contextvars
import copy
import dataclasses
import functools
import os
import pathlib
import re
import typing
import weakref

import networkx as nx

import footing.config
import footing.utils


# Thread/async safe stack for contextual classes
_context_stack = contextvars.ContextVar("context_stack")


class Callable:
    def __call__(self, *args, **kwargs):
        return self.call(*args, **kwargs)

    def call(self):
        raise NotImplementedError


class Contextual:
    def __post_init__(self):
        if not _context_stack.get(None):
            _context_stack.set(weakref.WeakKeyDictionary())

        _context_stack.get()[self] = []

    @contextlib.contextmanager
    def ctx(self):
        raise NotImplementedError

    def __enter__(self):
        ctx = self.ctx()
        _context_stack.get()[self].append(ctx)
        return ctx.__enter__()

    def __exit__(self, *args, **kwargs):
        ctx = _context_stack.get()[self].pop()
        ctx.__exit__(*args, **kwargs)


class Factory:
    @classmethod
    def factory(cls, val, /, *, defaults=None):
        defaults = defaults or {}
        return cls(**(defaults | val))


@dataclasses.dataclass(frozen=True)
class Uri:
    name: str
    type: str

    @property
    def uri(self):
        return f"{self.type}.{self.name}"


@dataclasses.dataclass(frozen=True)
class Artifact(Uri, Factory):
    path: str = None

    @classmethod
    def factory(cls, val, /, *, defaults=None):
        match val:
            case str() as str_val if re.search(r"[\?\*\[\]]", str_val):
                kwargs = {"name": val, "type": "glob", "path": val}
            case str():
                kwargs = {"name": val, "type": "file", "path": val}
            case dict():
                kwargs = val
            case _:
                raise ValueError(f'Invalid artifact - "{val}"')

        return super().factory(kwargs, defaults=defaults)


@dataclasses.dataclass(frozen=True)
class Task(Uri, Callable, Factory):
    _input: typing.Tuple[Artifact] = dataclasses.field(default_factory=tuple)
    _output: typing.Tuple[Artifact] = dataclasses.field(default_factory=tuple)
    _upstream: typing.Tuple["Task"] = dataclasses.field(default_factory=tuple)
    type = "task"  # Intentionally use a class variable for task types

    @property
    def input(self):
        return self._input

    @property
    def output(self):
        return self._output

    @property
    def upstream(self):
        return self._upstream

    @classmethod
    def from_config(cls, name, /):
        cfg = footing.config.find(f"{cls.type}.{name}")
        return cls.factory(cfg, defaults={"name": name})

    @property
    def edges(self):
        for u in self.upstream:
            yield Edge(upstream=u, downstream=self)
            yield from u.edges

    @property
    def graph(self):
        edges = tuple(self.edges)
        tasks = [e.upstream for e in edges] + [e.downstream for e in edges] + [self]
        return Graph(edges=edges, tasks=tuple(set(tasks)))


@dataclasses.dataclass(frozen=True)
class Edge:
    upstream: Task
    downstream: Task


@dataclasses.dataclass(frozen=True)
class Graph(Callable):
    edges: typing.Tuple[Edge]
    tasks: typing.Tuple[Task]

    def call(self):
        g = nx.DiGraph()
        g.add_nodes_from((t.uri, {"task": t}) for t in set(self.tasks))
        g.add_edges_from((e.upstream.uri, e.downstream.uri) for e in set(self.edges))

        for n in nx.topological_sort(g):
            g.nodes[n]["task"]()


@dataclasses.dataclass(frozen=True)
class Registry(Factory):
    name: str
    type: str
    channel: str = None

    def __post_init__(self):
        if self.type == "conda" and not self.channel:
            raise ValueError("Must supply channel when using conda registry")

    @classmethod
    def factory(cls, val, /, *, defaults=None):
        match val:
            case "pypi":
                kwargs = {"name": val, "type": val}
            case "conda-forge":
                kwargs = {"name": val, "type": "conda", "channel": "conda-forge"}
            case _:
                raise ValueError(f'Invalid registry "{val}"')

        return super().factory(kwargs, defaults=defaults)

    def install(self, packages):
        install_strs = " ".join(f'"{package.package}"' for package in packages)

        match self.type:
            case "conda":
                footing.utils.run(
                    f"{footing.utils.conda_exe()} install -y {install_strs} -c {self.channel}"
                )
            case "pypi":
                footing.utils.run(f"pip install {install_strs}")
            case _:
                raise AssertionError()


@dataclasses.dataclass(frozen=True)
class Package(Factory):
    package: str
    registry: Registry

    @classmethod
    def factory(cls, val, /, *, defaults=None):
        match val:
            case str():
                kwargs = {"package": val}
            case dict():
                kwargs = copy.copy(val)
                if "registry" in kwargs:
                    kwargs["registry"] = Registry.factory(kwargs["registry"])
            case _:
                raise TypeError(f'Invalid package type "{type(val)}"')

        return super().factory(kwargs, defaults=defaults)


@dataclasses.dataclass(frozen=True)
class CondaEnv(Artifact):
    type: str = "conda_env"


@dataclasses.dataclass(frozen=True, kw_only=True)
class Kit(Task, Contextual):
    type: str = "kit"
    packages: typing.Tuple[Package]

    @classmethod
    def factory(cls, val, /, *, defaults=None):
        # Load the default registry
        default_registry_name = val.get("registry", "conda-forge")
        default_registry = Registry.factory(default_registry_name)

        kwargs = val | {
            "packages": tuple(
                Package.factory(package, defaults={"registry": default_registry})
                for package in val.get("packages", [])
            )
        }

        return super().factory(kwargs, defaults=defaults)

    @functools.cached_property
    def _conda_env(self):
        path = footing.utils.toolkit_path() / footing.utils.hash128(
            self, footing.utils.detect_platform()
        )
        return CondaEnv(name=self.name, path=path)

    @property
    def output(self):
        return [self._conda_env()]

    @contextlib.contextmanager
    def ctx(self):
        prefix = pathlib.Path(self._conda_env.path)
        with footing.ctx.set(
            env={
                "PATH": f'{prefix / "bin"}:{os.environ.get("PATH", "")}',
                "CONDA_PREFIX": str(prefix),
                "CONDA_DEFAULT_ENV": str(prefix.name),
            }
        ):
            yield

    def call(self):
        """Build the toolkit, utilizing the cache if necessary"""
        footing.utils.conda_cmd(f"create -q -y -p {self._conda_env.path}")

        packages_by_registry = collections.defaultdict(list)
        for package in self.packages:
            packages_by_registry[package.registry].append(package)

        with self:
            for registry, packages in packages_by_registry.items():
                registry.install(packages)

        return [self._conda_env]


@dataclasses.dataclass(frozen=True, kw_only=True)
class Op(Task):
    type: str = "op"
    command: str
    kit: Kit = None

    @classmethod
    def factory(cls, val, /, *, defaults=None):
        kit = Kit.from_config(val["kit"]) if "kit" in val else None

        input = val.get("input") or []
        input = [input] if isinstance(input, str) else input
        output = val.get("output") or []
        output = [output] if isinstance(output, str) else output
        upstream = [cls.from_config(i[1:].strip()) for i in input if i.startswith("^")]
        if kit:
            upstream.append(kit)

        input = [Artifact.factory(i) for i in input if not i.startswith("^")]
        for u in upstream:
            input.extend(u._output)

        output = [Artifact.factory(o) for o in output]

        kwargs = {
            "kit": kit,
            "command": val["command"],
            "_input": tuple(input),
            "_output": tuple(output),
            "_upstream": tuple(upstream),
        }
        return super().factory(kwargs, defaults=defaults)

    def call(self):
        with contextlib.ExitStack() as stack:
            if self.kit:
                stack.enter_context(self.kit)

            footing.utils.run(self.command)
