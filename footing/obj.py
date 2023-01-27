import contextlib
import dataclasses
import functools
import os
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
class Entry:
    method: typing.Any


@dataclasses.dataclass
class CachedBuild:
    hash: str


@dataclasses.dataclass
class Obj:
    """A core footing object"""

    ###
    # Cached properties. We use private variables so that they aren't hashed
    ###

    def clear_cached_properties(self):
        """Clear all cached properties"""
        for field in dir(self.__class__):
            val = getattr(self.__class__, field)
            if isinstance(val, functools.cached_property):
                try:
                    delattr(self, field)
                except AttributeError:
                    pass  # Thrown when cached property has not yet been computed

    @functools.cached_property
    def _ref(self):
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

    @property
    def ref(self):
        return self._ref

    ###
    # Other properties
    ###

    @property
    def entry(self):
        return {}

    @property
    def name(self):
        """The configured name of this object"""
        return getattr(self, "_name", None)

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

    ###
    # Other core methods
    ###

    def lazy_post_init(self):
        """__post_init__ but lazy"""
        pass

    def render(self):
        """Compute dynamically rendered attributes"""
        self.lazy_post_init()
        self.clear_cached_properties()
        return self


@dataclasses.dataclass
class File:
    file_path: str
