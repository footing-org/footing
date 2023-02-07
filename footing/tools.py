import contextlib
import dataclasses
import functools
import os
import pathlib
import shutil
import typing

import xxhash

import footing.core
import footing.utils


@dataclasses.dataclass(kw_only=True)
class Install(footing.core.Task):
    packages: typing.List[str]
    channels: typing.List[str] = dataclasses.field(default_factory=lambda: ["conda-forge"])

    def __post_init__(self):
        packages = " ".join(self.packages)
        channels = " ".join(f"-c {c}" for c in self.channels)
        self.cmd = [f"{footing.utils.conda_exe()} install -y {packages} {channels}"]


@dataclasses.dataclass
class CachedBuild(footing.core.CachedBuild):
    path: str
    hash: str


@dataclasses.dataclass
class Toolkit(footing.core.Task):
    conda_env_root: str = None
    platform: str = None
    editable: bool = False

    def lazy_init(self):
        self.conda_env_root = self.conda_env_root or str(footing.utils.conda_root_path() / "envs")
        self.platform = self.platform or footing.utils.detect_platform()
        # TODO: Make the _create_conda_env a task that depends on the original input of the
        # toolkit. This is a better representation of the dependency DAG that supports parallelization
        self.input += [footing.core.Callable(self._create_conda_env)]
        self.ctx += [footing.core.Callable(self.enter)]

    ###
    # Cached properties. We use private variables so that they aren't hashed
    ###

    @functools.cached_property
    def _conda_env_name(self):
        # TODO: Ensure names from other projects don't collide when choosing an env name.
        name = self.name or self.ref.hash
        if self.name or self.editable:
            name += f"-{xxhash.xxh32_hexdigest(str(pathlib.Path.cwd()))}"

        return name

    @property
    def conda_env_name(self):
        return self._conda_env_name

    ###
    # Other properties
    ###

    @property
    def entry(self):
        return super().entry | {
            "main": footing.core.Entry(method=self.__call__),
        }

    @property
    def conda_env_path(self):
        return pathlib.Path(self.conda_env_root) / self.conda_env_name

    @property
    def cache_key(self):
        return self.conda_env_name

    @property
    def cache_obj(self):
        return CachedBuild(hash=self.ref.hash, path=str(self.conda_env_path))

    @property
    def is_cacheable(self):
        return True

    ###
    # Core methods and properties
    ###

    @contextlib.contextmanager
    def enter(self):
        with footing.utils.patch_conda_env(self.conda_env_path):
            yield

    @property
    def bin(self):
        """Return a task that directly references a binary"""
        return ToolkitBinFolder(toolkit=self)

    def __truediv__(self, cmd):
        """The / operator

        Returns a task that's executed within the toolkit
        """
        return footing.core.Task(cmd=[cmd], ctx=[self])

    def _create_conda_env(self):
        """Ran during the very end of input when running the toolkit task"""
        if "_ref" in self.__dict__:
            # The ref might have changed as a result of running input.
            # Clear the cached ref just in case
            del self._ref

        # TODO: Find a better way to shorten environment names and avoid global
        # collisions
        if len(str(self.conda_env_path)) > 113:
            raise RuntimeError(
                f"The installation path of this toolkit is too long ({len(self.conda_env_path)} > 113)."
                " Try shortening your toolkit name."
            )

        # Create the env and run installers
        footing.utils.conda_cmd(f"create -q -y -p {self.conda_env_path}")


@dataclasses.dataclass(kw_only=True)
class ToolkitBinFolder(footing.core.Task):
    toolkit: Toolkit

    def lazy_init(self):
        self.deps += [self.toolkit]
        self.cmd += [f"ls {self.toolkit.conda_env_path / 'bin'}"]

    def __truediv__(self, bin):
        """The / operator

        Returns a binary command within the bin folder
        """
        return ToolkitBin(toolkit=self.toolkit, bin=bin)


@dataclasses.dataclass(kw_only=True)
class ToolkitBin(footing.core.Task):
    toolkit: Toolkit
    bin: str

    def lazy_init(self):
        self.deps += [self.toolkit]
        self.cmd += [str(self.toolkit.conda_env_path / "bin" / self.bin)]
