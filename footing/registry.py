import dataclasses
import pathlib

import yaml

import footing.build
import footing.util


@dataclasses.dataclass
class Registry:
    name: str
    kind: str
    unversioned: list = dataclasses.field(default_factory=list)
    _def: dict = None

    def __post_init__(self):
        self.load()
        self._index = self._index or {"packages": {}}

    @property
    def index(self):
        return self._index

    @property
    def packages(self):
        return self.index["packages"]

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

    def package_key(self, *, kind, name, ref):
        """Get the key for a package"""
        key = f"{kind}:{name}"
        if kind not in self.unversioned:
            key += f":{ref}"

        return key

    def find(self, *, kind, name, ref):
        package = self.packages.get(self.package_key(kind=kind, name=name, ref=ref))
        if not package or ref != package["ref"]:
            return None

        package = Package(build=footing.build.Build.from_def(package), registry=self)
        if not self._exists(package):
            return None

        return package

    def push(self, build, copy=True):
        raise NotImplementedError

    def pull(self, build, output_path):
        raise NotImplementedError


@dataclasses.dataclass
class Package:
    build: footing.build.Build
    registry: Registry

    def pull(self, output_path):
        return self.registry.pull(self.build, output_path)


@dataclasses.dataclass
class FileSystemRegistry(Registry):
    @property
    def path(self):
        raise NotImplementedError

    def load(self):
        try:
            with open(self._resolve_path("index.yml"), "r") as index_file:
                self._index = yaml.load(index_file, Loader=yaml.SafeLoader)
        except FileNotFoundError:
            self._index = {}

    def _resolve_path(self, path):
        if pathlib.Path(path).is_absolute():
            return pathlib.Path(path)
        else:
            return self.path / path

    def _exists(self, package):
        return self._resolve_path(package.build.path).exists()

    def push(self, build, copy=True):
        assert build.path
        if copy and build.path.is_dir():
            raise ValueError("Cannot copy directories")

        package_key = self.package_key(kind=build.kind, name=build.name, ref=build.ref)

        package = Package(
            build=footing.build.Build(
                kind=build.kind,
                name=build.name,
                ref=build.ref,
                path=build.path.resolve() if not copy else package_key,
            ),
            registry=self,
        )

        # TODO: Implement atomicity
        # TODO: Store relative paths in the index
        if copy:
            footing.util.copy_file(build.path, self._resolve_path(package_key))

        self.index["packages"][package_key] = dataclasses.asdict(package.build)
        footing.util.yaml_dump(self.index, self._resolve_path("index.yml"))

        return package

    def pull(self, build, output_path):
        src = self._resolve_path(build.path)

        if src.is_dir():
            raise ValueError("Cannot pull directories")

        footing.util.copy_file(src, output_path)

        # TODO: Make copying builds easier
        return footing.build.Build(
            kind=build.kind, name=build.name, ref=build.ref, path=output_path
        )


@dataclasses.dataclass
class LocalRegistry(FileSystemRegistry):
    name: str = "default"
    kind: str = "local"
    unversioned: list = dataclasses.field(default_factory=lambda: ["toolkit"])

    @property
    def path(self):
        return footing.util.local_cache_dir() / "registry"


@dataclasses.dataclass
class RepoRegistry(FileSystemRegistry):
    name: str = "default"
    kind: str = "repo"
    unversioned: list = dataclasses.field(default_factory=lambda: ["toolkit-lock"])

    @property
    def path(self):
        return footing.util.repo_cache_dir() / "registry"


def local():
    return LocalRegistry()


def repo():
    return RepoRegistry()
