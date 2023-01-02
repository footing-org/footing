import copy
import dataclasses
import pathlib
import shutil

import yaml

import footing.build
import footing.util


@dataclasses.dataclass
class Registry:
    name: str
    kind: str
    versioned: bool = True
    _def: dict = None

    def __post_init__(self):
        self.load()

    @property
    def index(self):
        return self._index or {}

    @property
    def packages(self):
        return self.index.get("packages", {})

    @classmethod
    def from_def(cls, registry):
        return cls(_def=registry, **registry)

    @classmethod
    def from_local(cls):
        return cls(name="default", kind="local")

    @classmethod
    def from_repo(cls):
        return cls(name="default", kind="repo")

    def load(self):
        # Load self._index
        raise NotImplementedError

    def _exists(self, package):
        """Return True if the package exists.

        For example, a local path might have been deleted, causing the build to no longer
        be valid in the registry
        """
        raise NotImplementedError()

    def package_key(self, build):
        """Get the key for a package"""
        key = f"{build.kind}:{build.name}"
        if self.versioned:
            key += f":{build.ref}"

        return key

    def find(self, build):
        package = self.packages.get(self.package_key(build))
        if not package or build.ref != package["ref"]:
            return None

        package = Package(build=footing.build.Build.from_def(package), registry=self)
        if not self._exists(package):
            return None

        return package


@dataclasses.dataclass
class Package:
    build: footing.build.Build
    registry: Registry


@dataclasses.dataclass
class FileSystemRegistry(Registry):
    @property
    def path(self):
        raise NotImplementedError

    def load(self):
        try:
            with open(self.path / "index.yml", "r") as index_file:
                self._index = yaml.load(index_file, loader=yaml.SafeLoader)
        except FileNotFoundError:
            self._index = {}

    def _exists(self, package):
        return pathlib.Path(package.build.path).exists()

    def push(self, build):
        assert build.path
        package_key = self.package_key(build)
        package = Package(build=copy.deepcopy(build), registry=self)
        package.build.path = self.path / package_key

        # TODO: Implement atomicity
        shutil.copy(build.path, package.build.path)
        self.index["packages"][self.package_key(build)] = dataclasses.asdict(package.build)

        # TODO: Write index

        return package


@dataclasses.dataclass
class LocalRegistry(FileSystemRegistry):
    name: str = "default"
    kind: str = "local"

    @property
    def path(self):
        return footing.util.local_cache_dir() / "registry"


@dataclasses.dataclass
class RepoRegistry(FileSystemRegistry):
    name: str = "default"
    kind: str = "repo"
    versioned: bool = False

    @property
    def path(self):
        return footing.util.repo_cache_dir() / "registry"


def local():
    return LocalRegistry()


def repo():
    return RepoRegistry()
