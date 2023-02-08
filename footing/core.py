import contextlib
import dataclasses
import itertools
import re
import typing
import uuid

import orjson

import footing.config
import footing.utils


@dataclasses.dataclass
class Entry:
    method: typing.Any


@dataclasses.dataclass
class Artifact:
    _artifact_uuid: str = dataclasses.field(default_factory=uuid.uuid4)

    # Used to extract artifacts from serialized objects
    _uuid_re = re.compile(rb'{"_artifact_uuid":"(?P<artifact_uuid>.*?)"}')
    _registry = {}  # Global registry of artifacts

    def __post_init__(self):
        self._registry[self._artifact_uuid] = self


@dataclasses.dataclass(kw_only=True)
class Path(Artifact):
    """A filesystem path"""

    path: str


@dataclasses.dataclass
class Obj(footing.config.Configurable):
    """A core footing object"""

    def __post_init__(self):
        serialized = orjson.dumps(self)
        self._obj_hash = footing.utils.hash128(serialized)

    @property
    def obj_hash(self):
        return self._obj_hash

    @property
    def cli(self):
        return {}


@dataclasses.dataclass
class Callable:
    """A serializable lazy callable that can be used in footing tasks"""

    _callable: typing.Callable
    _args: typing.List[typing.Any] = dataclasses.field(default_factory=list)
    _kwargs: typing.Dict[str, typing.Any] = dataclasses.field(default_factory=dict)

    def __call__(self):
        return self._callable(*self._args, **self._kwargs)

    def __enter__(self):
        if hasattr(self, "_cm"):
            raise RuntimeError("Callable is not re-entrant")

        self._cm = self()
        return self._cm.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        self._cm.__exit__(exc_type, exc_value, traceback)
        del self._cm


def call(cmd):
    if isinstance(cmd, str):
        footing.cli.pprint(cmd.removeprefix(footing.utils.conda_exe() + " "))

    if isinstance(cmd, str):
        footing.utils.run(cmd)
    elif callable(cmd):
        cmd()
    else:
        raise ValueError(f'Invalid command - "{cmd}"')


@dataclasses.dataclass
class Task(Obj):
    cmd: typing.List[typing.Union[str, "Task", Callable]] = dataclasses.field(default_factory=list)
    input: typing.List[typing.Union["Task", Artifact]] = dataclasses.field(default_factory=list)
    output: typing.List[Artifact] = dataclasses.field(default_factory=list)
    ctx: typing.List[typing.Union["Task", Callable]] = dataclasses.field(default_factory=list)
    deps: typing.List["Task"] = dataclasses.field(default_factory=list)

    @property
    def cli(self):
        return {
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

    def call(self):
        """Main implementation for calling object"""
        with contextlib.ExitStack() as stack:
            for ctx in self.ctx:
                stack.enter_context(ctx)

            for cmd in itertools.chain(self.deps, self.ctx, self.input, self.cmd):
                if not isinstance(cmd, Artifact):
                    call(cmd)
