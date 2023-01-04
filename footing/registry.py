import dataclasses
import os
import pathlib

import boto3
import docker
import yaml

import footing.build
import footing.util


@dataclasses.dataclass
class Registry:
    name: str
    kind: str
    path: pathlib.Path = None
    unversioned: list = dataclasses.field(default_factory=list)
    _def: dict = None

    @property
    def uri(self):
        return f"{self.kind}:{self.name}"

    def __post_init__(self):
        self.load()
        self._index = getattr(self, "_index", None) or {"packages": {}}
        self.path = pathlib.Path(self.path)

    @property
    def index(self):
        return self._index

    @property
    def packages(self):
        return self.index["packages"]

    def load(self):
        # Load self._index
        pass

    def exists(self, build):
        if build.kind == "image":
            client = docker.from_env()
            return client.images.get(str(build.path)) is not None
        else:
            return self.resolve(build.path).exists()

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
            return self.path / path

    def load(self):
        try:
            with open(self.resolve("index.yml"), "r") as index_file:
                self._index = yaml.load(index_file, Loader=yaml.SafeLoader)
        except FileNotFoundError:
            self._index = {}

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
                path=build.path if not copy else package_name,
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
    path: pathlib.Path = dataclasses.field(
        default_factory=lambda: footing.util.local_cache_dir() / "registry"
    )
    unversioned: list = dataclasses.field(default_factory=lambda: ["toolkit"])


@dataclasses.dataclass
class RepoRegistry(FileSystemRegistry):
    name: str = "repo"
    path: pathlib.Path = dataclasses.field(
        default_factory=lambda: footing.util.repo_cache_dir() / "registry"
    )
    unversioned: list = dataclasses.field(default_factory=lambda: ["toolkit-lock"])


@dataclasses.dataclass
class ContainerRegistry(Registry):
    kind: str = "container"

    @property
    def client(self):
        return docker.from_env()

    def push(self, build, copy=True):
        image = self.client.images.get(str(build.path))
        assert image
        image.tag(f"{self.path}/{build.name}", force=True)
        auth_config = {
            "username": os.environ.get(f"FOOTING_AUTH_REGISTRY_dockerhub_USER"),
            "password": os.environ.get(f"FOOTING_AUTH_REGISTRY_dockerhub_PASS"),
        }
        self.client.images.push(
            f"{self.name}/{build.name}",
            auth_config=auth_config,
        )


@dataclasses.dataclass
class S3Registry(Registry):
    kind: str = "s3"

    @property
    def client(self):
        return docker.from_env()

    def upload_to_s3(self, local_dir):
        """Upload a directory to S3

        Contents of local_dir will appear under bucket/base_s3_dir

        Args:
            local_dir (str): The local directory to be uploaded
            bucket (str): The S3 bucket
            base_s3_dir (str): The base S3 directory to which uploads will go
        """
        import magic
        boto_s3 = boto3.resource("s3")
        bucket = str(self.path)
        base_s3_dir = None
        mime = magic.Magic(mime=True)

        for root, _, files in os.walk(local_dir):
            for name in files:
                local_p = os.path.join(root, name)
                relative_p = os.path.relpath(local_p, local_dir)
                s3_path = os.path.join(base_s3_dir, relative_p) if base_s3_dir else relative_p

                # python-magic doesnt accurately deal with CSS filesg
                if local_p.endswith(".css"):
                    content_type = "text/css"
                else:
                    content_type = mime.from_file(local_p)

                obj = boto_s3.Object(bucket, s3_path)
                print(f"uploading {local_p} to {bucket}/{s3_path}...")
                obj.upload_file(local_p, ExtraArgs={"ContentType": content_type})

    def push(self, build, copy=True):
        self.upload_to_s3(str(build.path))


def local():
    return LocalRegistry()


def repo():
    return RepoRegistry()


def from_def(registry):
    if registry["kind"] == "container":
        return ContainerRegistry(_def=registry, **registry)
    elif registry["kind"] == "s3":
        return S3Registry(_def=registry, **registry)
    else:
        raise NotImplementedError


def get(name):
    if name == "local":
        return local()
    elif name == "repo":
        return repo()
    else:
        config = footing.util.local_config()

        for registry in config["registries"]:
            if registry["name"] == name:
                return from_def(registry)


def up(*names):
    """Create registries"""
