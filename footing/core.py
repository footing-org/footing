import collections
import contextlib
import contextvars
import copy
import dataclasses
import functools
import glob
import os
import pathlib
import re
import typing
import weakref

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
class Obj(Uri, Factory):
    @classmethod
    def from_config(cls, name, /):
        cfg = footing.config.find(f"{cls.type}.{name}")
        return cls.factory(cfg, defaults={"name": name})


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

    def _hash_file(self, path):
        with open(path) as f:
            return footing.utils.hash128(f.read())

    def _mtime(self, path):
        try:
            return os.path.getmtime(path)
        except FileNotFoundError:
            return None

    def hash(self):
        match self.type:
            case "file":
                return self._hash_file(self.path)
            case "glob":
                val = "-".join(
                    sorted(
                        f"{file}:{self._mtime(file)}"
                        for file in glob.glob(self.path, recursive=True)
                    )
                )
                return footing.utils.hash128(val)
            case _:
                raise RuntimeError(f'Cannot hash type - "{self.type}"')


@dataclasses.dataclass(frozen=True)
class Task(Obj, Callable):
    input: typing.Tuple[Artifact] = dataclasses.field(default_factory=tuple)
    output: typing.Tuple[Artifact] = dataclasses.field(default_factory=tuple)
    _upstream: typing.Tuple["Task"] = dataclasses.field(default_factory=tuple)
    _cacheable: bool = True

    def hash(self):
        return footing.utils.hash128(self, *[i.hash() for i in self.input])

    def ref(self):
        return footing.utils.hash128(self.hash(), *[o.hash() for o in self.output])

    @property
    def upstream(self):
        return self._upstream

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


@dataclasses.dataclass(frozen=True)
class Runner(Callable):
    graph: Graph

    @property
    def cache_path(self):
        return pathlib.Path(".footing") / "cache"

    def cached_ref_path(self, task):
        return self.cache_path / "ref" / task.uri

    def cached_ref(self, task):
        try:
            with open(self.cached_ref_path(task)) as f:
                return f.read()
        except FileNotFoundError:
            return None

    def cache_ref(self, task):
        try:
            with open(self.cached_ref_path(task), "w") as f:
                f.write(task.ref())
        except FileNotFoundError:
            self.cached_ref_path(task).parent.mkdir(exist_ok=True, parents=True)
            return self.cached_ref_path(task)

    def run_task(self, task):
        """Runs a task, restoring from the cache if found"""
        # Check if the task is totally up to date
        if self.cached_ref(task) == task.ref():
            return
        else:
            task()

        self.cache_ref(task)

    def call(self):
        import networkx as nx  # TODO: Remove this dependency after implementing topological sort

        g = nx.DiGraph()
        g.add_nodes_from((t.uri, {"task": t}) for t in set(self.graph.tasks))
        g.add_edges_from((e.upstream.uri, e.downstream.uri) for e in set(self.graph.edges))

        for n in nx.topological_sort(g):
            self.run_task(g.nodes[n]["task"])


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

    def hash(self):
        return footing.utils.hash128(str(pathlib.Path(self.path).stat().st_mtime))


@dataclasses.dataclass(frozen=True, kw_only=True)
class Kit(Task, Contextual):
    packages: typing.Tuple[Package]
    type: str = "kit"

    @classmethod
    def factory(cls, val, /, *, defaults=None):
        defaults = defaults or {}
        name = val.get("name", defaults["name"])

        # Load the default registry
        default_registry_name = val.get("registry", "conda-forge")
        default_registry = Registry.factory(default_registry_name)

        def iter_packages(cfg):
            for p in cfg.get("packages", []):
                if p.startswith("^"):
                    yield from iter_packages(footing.config.find(f"kit.{p[1:].strip()}"))
                else:
                    yield p

        def package_name(install):
            name = re.match("[\w\-\.]+", install)
            if not name:
                raise ValueError(f"Invalid package name - {install}")

            return name.group().lower().replace(".", "_").replace("-", "_")

        packages = {package_name(package): package for package in iter_packages(val)}
        env_name = name + "-" + footing.utils.hash32(os.getcwd(), footing.utils.detect_platform())
        kwargs = val | {
            "packages": tuple(
                Package.factory(package, defaults={"registry": default_registry})
                for package in packages.values()
            ),
            "output": (CondaEnv(name=name, path=str(footing.utils.toolkit_path() / env_name)),),
        }

        return super().factory(kwargs, defaults=defaults)

    @functools.cached_property
    def _conda_env(self):
        return self.output[0]

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
        if not pathlib.Path(self._conda_env.path).exists():
            footing.utils.conda_cmd(f"create -q -y -p {self._conda_env.path}")

        packages_by_registry = collections.defaultdict(list)
        for package in self.packages:
            packages_by_registry[package.registry].append(package)

        with self:
            for registry, packages in packages_by_registry.items():
                registry.install(packages)

        pathlib.Path(self._conda_env.path).touch()

        return [self._conda_env]


@dataclasses.dataclass(frozen=True, kw_only=True)
class Op(Task):
    command: str
    kit: Kit = None
    type: str = "op"

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
            input.extend(u.output)

        output = [Artifact.factory(o) for o in output]

        kwargs = {
            "kit": kit,
            "command": val["command"],
            "input": tuple(input),
            "output": tuple(output),
            "_upstream": tuple(upstream),
        }
        return super().factory(kwargs, defaults=defaults)

    def call(self):
        with contextlib.ExitStack() as stack:
            if self.kit:
                stack.enter_context(self.kit)

            footing.utils.run(self.command)

        return self.output
