import contextlib
import dataclasses
import glob
import itertools
import os
import re
import shlex
import typing

import orjson

import footing.config
import footing.ctx
import footing.utils


@dataclasses.dataclass
class Entry:
    method: typing.Any


@dataclasses.dataclass
class Artifact:
    artifact_uuid: str = dataclasses.field()

    # Used to extract artifacts from serialized objects
    _uuid_re = re.compile(rb'{"artifact_uuid":"(?P<artifact_uuid>.*?)"')
    _registry = {}  # Global registry of artifacts

    def __post_init__(self):
        self._registry[self.artifact_uuid] = self

    @property
    def obj_hash(self):
        raise NotImplementedError


@dataclasses.dataclass(kw_only=True)
class Path(Artifact):
    """A filesystem path"""

    def mtime(self, file):
        try:
            return os.path.getmtime(file)
        except FileNotFoundError:
            return None

    @property
    def obj_hash(self):
        if mtime := self.mtime(self.artifact_uuid):
            return f"{self.artifact_uuid}:{mtime}"
        else:
            val = "-".join(
                sorted(
                    f"{file}:{self.mtime(file)}"
                    for file in glob.glob(self.artifact_uuid, recursive=True)
                )
            )

            if not val:
                val = f"{self.artifact_uuid}:none"

            return val


@dataclasses.dataclass
class Obj(footing.config.Configurable):
    """A core footing object"""

    def __post_init__(self):
        # TODO: Make post_init freeze all dataclass properties since the hash is computed here
        serialized = orjson.dumps(self)
        self._obj_hash = footing.utils.hash128(serialized)

        artifact_uuids = (
            file.decode("utf-8") for file in re.findall(Artifact._uuid_re, serialized)
        )
        self._artifacts = {
            artifact_uuid: Artifact._registry[artifact_uuid] for artifact_uuid in artifact_uuids
        }

    @property
    def obj_hash(self):
        return self._obj_hash

    @property
    def cli(self):
        return {}


@dataclasses.dataclass
class Lazy:
    """A serializable lazy callable for functions"""

    _obj: typing.Callable
    _args: typing.List[typing.Any] = dataclasses.field(default_factory=list)
    _kwargs: typing.Dict[str, typing.Any] = dataclasses.field(default_factory=dict)

    def __call__(self):
        return self._obj(*self._args, **self._kwargs)

    def __enter__(self):
        if hasattr(self, "_cm"):
            raise RuntimeError(f"{self} is not re-entrant")

        self._cm = self()
        return self._cm.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        self._cm.__exit__(exc_type, exc_value, traceback)
        del self._cm


@dataclasses.dataclass
class Cmd:
    cmd: str
    entry: bool = False

    def __post_init__(self):
        self.cmd = str(self.cmd)

    def __str__(self):
        cmd = self.cmd
        if self.entry and footing.ctx.get().subcommand:
            extra = shlex.join(footing.ctx.get().subcommand)
            cmd += f" {extra}"

        return cmd


@dataclasses.dataclass
class Task(Obj):
    cmd: typing.List[typing.Union[str, "Task", Lazy]] = dataclasses.field(default_factory=list)
    input: typing.List[typing.Union["Task", Artifact]] = dataclasses.field(default_factory=list)
    output: typing.List[Artifact] = dataclasses.field(default_factory=list)
    ctx: typing.List[typing.Union["Task", Lazy]] = dataclasses.field(default_factory=list)
    deps: typing.List["Task"] = dataclasses.field(default_factory=list)

    @property
    def artifacts(self):
        # Output can be modified after __post_init__. Dynamically include those artifacts here
        return (
            self._artifacts | {output.artifact_uuid: output for output in self.output}
        ).values()

    @property
    def cli(self):
        return super().cli | {
            "main": Entry(method=self.__call__),
        }

    def __enter__(self):
        if hasattr(self, "_cm"):
            raise RuntimeError(f"Object is not re-entrant")

        self._cm = self.enter()
        return self._cm.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        self._cm.__exit__(exc_type, exc_value, traceback)
        del self._cm

    def __call__(self):
        return self.call()

    def __truediv__(self, other):
        return self.div(other)

    @contextlib.contextmanager
    def enter(self):
        """Main implementation for entering object"""
        yield

    def div(self, obj):
        """Main implementation for the slash operator"""
        return Task(cmd=[obj], ctx=[self])

    def exec(self, cmd):
        """Main implementation for executing a command"""
        if isinstance(cmd, Lazy):
            cmd = cmd()

            # If the lazy object doesn't return a Cmd, we're done
            # running
            if not isinstance(cmd, Cmd):
                return

        if isinstance(cmd, Cmd):
            cmd = str(cmd)

        if isinstance(cmd, str):
            footing.cli.pprint(cmd.removeprefix(footing.utils.conda_exe() + " "))
            footing.utils.run(cmd)
        elif callable(cmd):
            cmd()
        else:
            raise RuntimeError(f'Invalid command - "{cmd}"')

    def call(self):
        """Main implementation for calling object"""
        if self.is_cached:
            return

        with contextlib.ExitStack() as stack:
            for ctx in self.ctx:
                stack.enter_context(ctx)

            for cmd in itertools.chain(self.deps, self.ctx, self.input, self.cmd):
                if not isinstance(cmd, Artifact):
                    self.exec(cmd)

        self.cache()

    ###
    # Caching
    ###

    @property
    def is_cacheable(self):
        return self.input or self.output

    @property
    def build_hash(self):
        return footing.utils.hash128(
            self.obj_hash + "".join(sorted(artifact.obj_hash for artifact in self.artifacts))
        )

    @property
    def build_cache_file(self):
        return footing.utils.install_path() / "cache" / self.build_hash

    def cache(self):
        if self.is_cacheable:
            try:
                self.build_cache_file.touch()
            except FileNotFoundError:
                self.build_cache_file.mkdir(parents=True, exist_ok=True)
                self.build_cache_file.touch()

    def uncache(self):
        self.build_cache_file.unlink(missing_ok=True)

    @property
    def is_cached(self):
        if footing.ctx.get().cache:
            return self.build_cache_file.exists() if self.is_cacheable else False
        else:
            return False


@dataclasses.dataclass
class Shell(Task):
    """Runs a shell if there are no commands.

    If entry=True, last command will be executed as entrypoint
    """

    entry: bool = False

    def __post_init__(self):
        if not self.cmd:
            self.cmd.append(Lazy(self.shell_cmd))

        if self.entry:
            self.cmd[-1] = Cmd(self.cmd[-1], entry=True)

        super().__post_init__()

    def shell_cmd(self):
        return Cmd(footing.utils.detect_shell()[1] or "bash")
