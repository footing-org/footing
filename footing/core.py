import contextlib
import copy
import dataclasses
import glob
import itertools
import os
import re
import shutil
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

    def rm(self):
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

    def rm(self):
        try:
            try:
                os.remove(self.artifact_uuid)
            except PermissionError:
                shutil.rmtree(self.artifact_uuid)
        except FileNotFoundError:
            pass


@dataclasses.dataclass
class Obj(footing.config.Configurable):
    """A core footing object"""

    def freeze(self):
        """Freeze the object hash and artifacts"""
        serialized = orjson.dumps(self)
        self._obj_hash = footing.utils.hash128(serialized)

        artifact_uuids = (
            file.decode("utf-8") for file in re.findall(Artifact._uuid_re, serialized)
        )
        self._artifacts = {
            artifact_uuid: Artifact._registry[artifact_uuid] for artifact_uuid in artifact_uuids
        }

    def unfreeze(self):
        try:
            delattr(self, "_obj_hash")
            delattr(self, "_artifacts")
        except AttributeError:
            pass

    @property
    def obj_hash(self):
        if not hasattr(self, "_obj_hash"):
            self.freeze()

        return self._obj_hash

    @property
    def artifacts(self):
        if not hasattr(self, "_artifacts"):
            self.freeze()

        return self._artifacts.values()

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
        cmd = str(self.cmd)
        if self.entry and footing.ctx.get().entry_add:
            cmd += f" {footing.ctx.get().entry_add}"

        self.cmd = cmd

    def __str__(self):
        return self.cmd


def exec(cmd):
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


@dataclasses.dataclass
class Task(Obj):
    cmd: typing.List[typing.Union[str, "Task", Lazy]] = dataclasses.field(default_factory=list)
    input: typing.List[typing.Union["Task", Artifact]] = dataclasses.field(default_factory=list)
    output: typing.List[Artifact] = dataclasses.field(default_factory=list)
    ctx: typing.List["Contextual"] = dataclasses.field(default_factory=list)
    deps: typing.List["Task"] = dataclasses.field(default_factory=list)

    def __post_init__(self):
        # When a task has multiple commands, they must reference each other as dependencies.
        # TODO: Consider using "groups" of commands that can be ANDed or ORed together to better
        # support this modeling. Here we do an AND
        if len(self.cmd) > 1:
            ref_cmd = []
            for i, cmd in enumerate(self.cmd):
                if i > 0:
                    if isinstance(cmd, Task):
                        cmd = copy.copy(cmd)
                        cmd.deps += [self.cmd[i - 1]]
                    else:
                        cmd = Task(cmd=[cmd], deps=[self.cmd[i - 1]])

                ref_cmd.append(cmd)
            self.cmd = ref_cmd

    @property
    def cli(self):
        return super().cli | {
            "main": Entry(method=self.__call__),
        }

    def __call__(self):
        return self.call()

    def call(self):
        """Main implementation for calling object"""
        if footing.ctx.get().debug:
            footing.cli.pprint(
                f"run={self.config_name or self.output or self.__class__.__name__} obj_hash={self.obj_hash} run_hash={self.run_hash} is_cached={self.is_cached}"
            )

        if self.is_cached:
            return

        with contextlib.ExitStack() as stack:
            for ctx in self.ctx:
                stack.enter_context(ctx)

            for cmd in itertools.chain(self.deps, self.ctx, self.input, self.cmd):
                if not isinstance(cmd, Artifact):
                    exec(cmd)

        self.cache()

    ###
    # Caching
    ###

    @property
    def is_cacheable(self):
        return self.input or self.output

    @property
    def run_hash(self):
        return footing.utils.hash128(
            self.obj_hash + "".join(sorted(artifact.obj_hash for artifact in self.artifacts))
        )

    @property
    def run_cache_file(self):
        return footing.utils.cache_path() / "run" / self.run_hash

    def cache(self):
        if self.is_cacheable:
            self.freeze()  # Ensure the latest hash is computed when caching
            try:
                self.run_cache_file.touch()
            except FileNotFoundError:
                self.run_cache_file.parent.mkdir(parents=True, exist_ok=True)
                self.run_cache_file.touch()

    def uncache(self):
        self.run_cache_file.unlink(missing_ok=True)

    @property
    def is_cached(self):
        if footing.ctx.get().cache:
            return self.run_cache_file.exists() if self.is_cacheable else False
        else:
            return False


class Contextual:
    """A mixin for tasks that can modify the execution environment"""

    def __enter__(self):
        if hasattr(self, "_cm"):
            raise RuntimeError(f"Object is not re-entrant")

        self._cm = self.enter()
        return self._cm.__enter__()

    @contextlib.contextmanager
    def enter(self):
        """Main implementation for entering object"""
        yield

    def __exit__(self, exc_type, exc_value, traceback):
        self._cm.__exit__(exc_type, exc_value, traceback)
        del self._cm

    def __truediv__(self, other):
        return self.div(other)

    def div(self, obj):
        """Main implementation for the slash operator"""
        return Task(cmd=[obj], ctx=[self])


@dataclasses.dataclass(kw_only=True)
class Clear(Task):
    """Clears the cache for a given task"""

    task: Task

    def __post_init__(self):
        self.cmd.append(Lazy(self.clear))

        super().__post_init__()

    def clear(self):
        self.task.uncache()


@dataclasses.dataclass(kw_only=True)
class Rm(Task):
    """Remove the artifacts for a given task and clear the cache"""

    task: Task

    def __post_init__(self):
        self.cmd.append(Lazy(self.rm))

        super().__post_init__()

    def rm(self):
        for output in self.task.output:
            output.rm()

        self.task.uncache()


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
