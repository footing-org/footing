import collections
import contextlib
import dataclasses
import functools
import os
import pathlib
import re
import typing

import footing.config
import footing.utils


@dataclasses.dataclass(frozen=True)
class Registry:
    name: str
    type: str
    channel: str = None

    def __post_init__(self):
        if self.type == "conda" and not self.channel:
            raise ValueError("Must supply channel when using conda registry")

    @classmethod
    def from_config(cls, val, /):
        match val:
            case "pypi":
                return cls(name=val, type=val)
            case "conda-forge":
                return cls(name=val, type="conda", channel="conda-forge")
            case other:
                raise ValueError(f'Invalid registry "{val}"')

    def install(self, packages):
        install_strs = ' '.join(f'"{package.install_str}"' for package in packages)

        match self.type:
            case "conda":
                footing.utils.run(
                    f"{footing.utils.conda_exe()} install -y {install_strs} -c {self.channel}"
                )
            case "pypi":
                footing.utils.run(f"pip install {install_strs}")
            case _:
                raise AssertionError()


@dataclasses.dataclass(frozen=True)
class Package:
    name: str
    registry: Registry
    version: str = "*"

    @classmethod
    def from_config(cls, name, val, /, *, defaults=None):
        cfg = footing.config.get()
        defaults = defaults or {}

        match val:
            case str():
                return cls(**(defaults | {"name": name, "version": val}))
            case dict():
                if "registry" in val:
                    val["registry"] = Registry.from_config(val["registry"])

                return cls(**(defaults | val))
            case _:
                raise TypeError(f'Invalid tool type "{type(val)}"')
            
    @property
    def install_str(self):
        match self.version:
            case "*":
                return f"{self.name}"
            case _ if re.match(self.version, r"^[><~=]"):
                return f"{self.name}{self.version}"
            case _:
                return f"{self.name}={self.version}" 


class Cacheable:
    @functools.cached_property
    def _obj_hash(self):  # All cached properties must be private variables
        return footing.utils.hash128(self)

    @property
    def run_cache_file(self):
        return footing.utils.cache_path() / "run" / self._obj_hash

    def cache(self):
        try:
            self.run_cache_file.touch()
        except FileNotFoundError:
            self.run_cache_file.parent.mkdir(parents=True, exist_ok=True)
            self.run_cache_file.touch()

    def uncache(self):
        self.run_cache_file.unlink(missing_ok=True)

    @property
    def is_cached(self):
        return self.run_cache_file.exists() if footing.ctx.get().cache else False


@dataclasses.dataclass(frozen=True)
class Shed(Cacheable):
    name: str
    packages: typing.Tuple[Package]
    root: str = dataclasses.field(default_factory=lambda: str(footing.utils.toolkit_path()))
    platform: str = dataclasses.field(default_factory=footing.utils.detect_platform)

    @classmethod
    def from_config(cls, name, val, /):
        # Load the default registry
        default_registry_name = val.get("registry", "conda-forge")
        default_registry = Registry.from_config(default_registry_name)
        defaults = {"registry": default_registry}

        return cls(
            name=name,
            packages=tuple(
                Package.from_config(name, val, defaults=defaults)
                for name, val in val.get("packages", {}).items()
            )
        )

    @property
    def venv_path(self):
        return pathlib.Path(self.root) / self._obj_hash

    @contextlib.contextmanager
    def enter(self):
        prefix = self.venv_path
        with footing.ctx.set(
            env={
                "PATH": f'{prefix / "bin"}:{os.environ.get("PATH", "")}',
                "CONDA_PREFIX": str(prefix),
                "CONDA_DEFAULT_ENV": str(prefix.name),
            }
        ):
            yield

    def build(self):
        """Build the toolkit, utilizing the cache if necessary"""
        if self.is_cached and self.venv_path.exists():
            return

        footing.utils.conda_cmd(f"create -q -y -p {self.venv_path}")

        packages_by_registry = collections.defaultdict(list)
        for package in self.packages:
            packages_by_registry[package.registry].append(package)

        with self.enter():
            for registry, packages in packages_by_registry.items():
                registry.install(packages)

        self.cache()
