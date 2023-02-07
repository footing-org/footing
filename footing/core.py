import contextlib
import dataclasses
import functools
import itertools
import re
import typing

import orjson
import xxhash

import footing.config
import footing.ctx
import footing.utils


FILE_PATH_RE = re.compile(rb'{"file_path":"(?P<file_name>.*?)"}')


def hash(val):
    return xxhash.xxh3_128_hexdigest(val)


def hash_file(path):
    try:
        with open(path) as f:
            return hash(f.read())
    except FileNotFoundError:
        return hash("Not Found")


@dataclasses.dataclass
class ObjRef:
    """A reference to an object"""

    obj_hash: str
    files: typing.List[str]
    hash: str


@dataclasses.dataclass
class FileRef:
    """A reference to a file"""

    mod: int
    hash: str


@dataclasses.dataclass
class Entry:
    method: typing.Any


@dataclasses.dataclass
class CachedBuild:
    hash: str


@dataclasses.dataclass
class Lazy:
    @property
    def is_initialized(self):
        return getattr(self, "_is_initialized", False)

    def lazy_init(self):
        pass

    def init(self):
        if not self.is_initialized:
            _lazy_init_inner(self)
            self._is_initialized = True

        return self


def _lazy_init_inner(obj):
    if hasattr(type(obj), "__dataclass_fields__"):
        for f in dataclasses.fields(obj):
            _lazy_init_inner(getattr(obj, f.name))

        if isinstance(obj, Lazy):
            if not obj.is_initialized:
                obj.lazy_init()
                obj._is_initialized = True

    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _lazy_init_inner(v)

    elif isinstance(obj, dict):
        for k, v in obj.items():
            _lazy_init_inner(k)
            _lazy_init_inner(v)

    return obj


@dataclasses.dataclass
class Obj(Lazy, footing.config.Configurable):
    """A core footing object"""

    ###
    # Cached properties. We use private variables so that they aren't hashed
    ###

    # @functools.cached_property
    @property
    def _ref(self):
        if not self.is_initialized:
            raise RuntimeError("Must initialize object before computing ref")

        serialized = orjson.dumps(self)
        files = sorted(file.decode("utf-8") for file in set(re.findall(FILE_PATH_RE, serialized)))
        full_hash = obj_hash = hash(serialized)
        if files:
            files_hash = "".join(hash_file(file) for file in files)
            full_hash = hash(obj_hash + files_hash)

        return ObjRef(obj_hash=obj_hash, files=files, hash=full_hash)

    @property
    def ref(self):
        return self._ref

    ###
    # Other properties
    ###

    @property
    def entry(self):
        return {}

    ###
    # Properties and methods for footing's cache
    ###

    @property
    def cache_key(self):
        return self.ref.hash

    @property
    def cache_obj(self):
        return CachedBuild(hash=self.ref.hash)

    def read_cache(self):
        obj_cls = self.cache_obj.__class__
        try:
            with open(footing.utils.install_path() / "cache" / self.cache_key, "r") as file:
                return obj_cls(**orjson.loads(file.read()))
        except Exception:
            return None

    def write_cache(self):
        cache_root = footing.utils.install_path() / "cache"
        cache_root.mkdir(exist_ok=True)
        with open(cache_root / self.cache_key, "wb") as file:
            file.write(orjson.dumps(self.cache_obj))

    def delete_cache(self):
        (footing.utils.install_path() / "cache" / self.cache_key).unlink(missing_ok=True)
        assert not (footing.utils.install_path() / "cache" / self.cache_key).exists()

    @property
    def is_cached(self):
        new_cache_obj = self.cache_obj
        old_cache_obj = self.read_cache()
        return old_cache_obj == new_cache_obj


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


def call_cmd(cmd):
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
    input: typing.List[typing.Union[str, "Task", Callable]] = dataclasses.field(
        default_factory=list
    )
    output: typing.List["Task"] = dataclasses.field(default_factory=list)
    ctx: typing.List[typing.Any] = dataclasses.field(default_factory=list)
    deps: typing.List["Task"] = dataclasses.field(default_factory=list)

    @property
    def entry(self):
        return {
            "main": Entry(method=self.__call__),
        }

    def __enter__(self):
        self.init()

        if hasattr(self, "_cm"):
            raise RuntimeError(f"Object is not re-entrant")

        self._cm = self.enter()
        return self._cm.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        self._cm.__exit__(exc_type, exc_value, traceback)
        del self._cm

    @contextlib.contextmanager
    def enter(self):
        """Main implementation for entering object"""
        yield

    def __call__(self):
        self.init()

        return self.call()

    @property
    def is_cacheable(self):
        return self.input or self.output

    def call(self):
        """Main implementation for calling object"""
        if self.is_cacheable and self.is_cached and footing.ctx.get().cache:
            return

        with contextlib.ExitStack() as stack:
            for ctx in self.ctx:
                stack.enter_context(ctx)

            for cmd in itertools.chain(self.deps, self.ctx, self.input, self.cmd):
                call_cmd(cmd)

        if self.is_cacheable:
            self.write_cache()


@dataclasses.dataclass
class Artifact(Obj):
    def __call__(self):
        pass


@dataclasses.dataclass
class File(Artifact):
    # file_path is a special name extracted and used to compute file hashes
    # during object hashing. Do not change this name without changing
    # FILE_PATH_RE
    file_path: str
