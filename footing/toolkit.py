import dataclasses
import functools
import os
import pathlib
import stat
import typing

import xxhash

import footing.obj
import footing.func
import footing.utils


@dataclasses.dataclass(kw_only=True)
class Conda(footing.func.Func):
    packages: typing.List[str]
    channels: typing.List[str] = dataclasses.field(default_factory=lambda: ["conda-forge"])

    @property
    def rendered(self):
        packages = " ".join(self.packages)
        channels = " ".join(f"-c {c}" for c in self.channels)
        return f"{footing.utils.conda_exe()} install -y {packages} {channels}"


@dataclasses.dataclass
class CachedBuild:
    path: str
    hash: str


@dataclasses.dataclass
class Toolkit(footing.obj.Obj):
    installers: typing.List[footing.func.Func]
    pre_install_hooks: typing.List[footing.func.Func] = dataclasses.field(default_factory=list)
    conda_env_root: str = None
    platform: str = None
    editable: bool = False

    def __post_init__(self):
        self.conda_env_root = self.conda_env_root or str(footing.utils.conda_root_path() / "envs")
        self.platform = self.platform or footing.utils.detect_platform()

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
        return {
            "build": footing.obj.Entry(method=self.build),
            "/": footing.obj.Entry(method=self.exec),
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

    ###
    # Core methods
    ###

    def exec(self, exe, args):
        """Execute an executable in this toolkit"""
        self.build()

        exe_bin = pathlib.Path(self.conda_env_root) / self.conda_env_name / "bin"
        if not exe:
            os.execvp("ls", ["ls", str(exe_bin)])

        exe_path = exe_bin / exe
        if not exe_path.exists():
            raise ValueError(f'Executable "{exe}" does not exist in this toolkit.')

        os.execv(str(exe_path), [exe] + args)

    def build(self):
        """Create a conda env with the tools installed"""
        self.render()

        # TODO: Find a better way to shorten environment names and avoid global
        # collisions
        if len(str(self.conda_env_path)) > 114:
            raise RuntimeError(
                f"The installation path of this toolkit is too long ({len(self.conda_env_path)} > 113)."
                " Try shortening your toolkit name."
            )

        if self.is_cached:
            if pathlib.Path(self.cache_obj.path).exists():
                # Cached
                return
            else:
                # The cached object is no longer valid. Remove it and continue
                self.delete_cache()

        # Run pre-install hooks.
        for func in self.pre_install_hooks:
            func.run()

        if self.pre_install_hooks:
            # The ref might have changed as a result of running pre-install hooks.
            # Clear cached properties just in case.
            self.clear_cached_properties()

        # Create the env and run installers
        footing.utils.conda_cmd(f"create -q -y -p {self.conda_env_path}")

        for installer in self.installers:
            installer.run(toolkit=self.conda_env_path)

        self.write_cache()

        # TODO: Warn when the hash has changed midway. This indicates an improper setup
