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

    @property
    def uri(self):
        return f"{self.kind}:{self.name}"

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

    @property
    def root(self):
        raise NotImplementedError

    def load(self):
        # Load self._index
        raise NotImplementedError

    def exists(self, build):
        """Return True if the build exists.

        For example, a local path might have been deleted, causing the build to no longer
        be valid in the registry
        """
        raise NotImplementedError()

    def package_name(self, *, kind, name, ref):
        """Get the name for a package"""
        name = f"{kind}:{name}"
        if kind not in self.unversioned:
            name += f":{ref}"

        return name

    def find(self, *, kind, name, ref):
        package = self.packages.get(self.package_name(kind=kind, name=name, ref=ref))
        if not package or ref != package["ref"]:
            return None

        package = Package(build=footing.build.Build.from_def(package), registry=self)
        if not self.exists(package.build):
            return None

        return package

    def push(self, build, copy=True):
        raise NotImplementedError

    def pull(self, build, output_path):
        raise NotImplementedError

    def resolve(self, path):
        raise NotImplementedError


@dataclasses.dataclass
class Package:
    build: footing.build.Build
    registry: Registry

    def resolve(self):
        return self.registry.resolve(self.build.path)

    def pull(self, output_path):
        return self.registry.pull(self.build, output_path)


@dataclasses.dataclass
class FileSystemRegistry(Registry):
    kind: str = "filesystem"

    def resolve(self, path):
        if pathlib.Path(path).is_absolute():
            return pathlib.Path(path)
        else:
            return self.root / path

    def load(self):
        try:
            with open(self.resolve("index.yml"), "r") as index_file:
                self._index = yaml.load(index_file, Loader=yaml.SafeLoader)
        except FileNotFoundError:
            self._index = {}

    def exists(self, build):
        return self.resolve(build.path).exists()

    def push(self, build, copy=True):
        assert build.path
        if copy and build.path.is_dir():
            raise ValueError("Cannot copy directories")

        package_name = self.package_name(kind=build.kind, name=build.name, ref=build.ref)

        package = Package(
            build=footing.build.Build(
                kind=build.kind,
                name=build.name,
                ref=build.ref,
                path=build.path.resolve() if not copy else package_name,
            ),
            registry=self,
        )

        # TODO: Implement atomicity
        # TODO: Store relative paths in the index
        if copy:
            footing.util.copy_file(build.path, self.resolve(package_name))

        self.index["packages"][package_name] = dataclasses.asdict(package.build)
        footing.util.yaml_dump(self.index, self.resolve("index.yml"))

        return package

    def pull(self, build, output_path):
        src = self.resolve(build.path)

        if src.is_dir():
            raise ValueError("Cannot pull directories")

        footing.util.copy_file(src, output_path)

        # TODO: Make copying builds easier
        return footing.build.Build(
            kind=build.kind, name=build.name, ref=build.ref, path=output_path
        )


@dataclasses.dataclass
class LocalRegistry(FileSystemRegistry):
    name: str = "local"
    unversioned: list = dataclasses.field(default_factory=lambda: ["toolkit"])

    @property
    def root(self):
        return footing.util.local_cache_dir() / "registry"


@dataclasses.dataclass
class RepoRegistry(FileSystemRegistry):
    name: str = "repo"
    unversioned: list = dataclasses.field(default_factory=lambda: ["toolkit-lock"])

    @property
    def root(self):
        return footing.util.repo_cache_dir() / "registry"


def local():
    return LocalRegistry()


def repo():
    return RepoRegistry()


def get(name):
    if name == "local":
        return local()
    elif name == "repo":
        return repo()

def ls():
    return [local(), repo()]

