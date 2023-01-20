import contextlib
import dataclasses
import re
import typing

import orjson
import xxhash

import footing.config
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
class Obj:
    """A core footing object"""

    @contextlib.contextmanager
    def cache_ref(self):
        """Ensure the ref is cached during the context manager"""
        self._cached_ref = None
        yield
        del self._cached_ref

    @property
    def ref(self):
        if getattr(self, "_cached_ref", None):
            return self._cached_ref

        serialized = orjson.dumps(self)
        files = sorted(file.decode("utf-8") for file in set(re.findall(FILE_PATH_RE, serialized)))
        full_hash = obj_hash = hash(serialized)
        if files:
            files_hash = "".join(hash_file(file) for file in files)
            full_hash = hash(obj_hash + files_hash)

        ref = ObjRef(obj_hash=obj_hash, files=files, hash=full_hash)

        if hasattr(self, "_cached_ref"):
            self._cached_ref = ref

        return ref

    def uncache_ref(self):
        if hasattr(self, "_cached_ref"):
            self._cached_ref = None

    @property
    def name(self):
        """The configured name of this object"""
        return getattr(self, "_name", None)

    @property
    def cache_key(self):
        return self.ref.hash

    def cache_read(self, obj_cls):
        try:
            with open(footing.utils.install_path() / "cache" / self.cache_key, "r") as file:
                return obj_cls(**orjson.loads(file.read()))
        except Exception:
            return None

    def cache_write(self, val):
        cache_root = footing.utils.install_path() / "cache"
        cache_root.mkdir(exist_ok=True)
        with open(cache_root / self.cache_key, "wb") as file:
            file.write(orjson.dumps(val))


@dataclasses.dataclass
class File:
    file_path: str