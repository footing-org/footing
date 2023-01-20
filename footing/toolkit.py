import base64
import dataclasses
import pathlib
import typing

import footing.obj
import footing.func
import footing.utils


@dataclasses.dataclass(kw_only=True)
class Conda(footing.func.Func):
    packages: typing.List[str]
    channels: typing.List[str] = dataclasses.field(default_factory=lambda: ["conda-forge"])

    @property
    def cmd(self):
        packages = " ".join(self.packages)
        channels = " ".join(f"-c {c}" for c in self.channels)
        return f"{footing.utils.conda_exe()} install -q -y {packages} {channels}"

    @cmd.setter
    def cmd(self, _):
        pass


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

    def __post_init__(self):
        self.conda_env_root = self.conda_env_root or str(footing.utils.conda_root_path() / "envs")
        self.platform = self.platform or footing.utils.detect_platform()

    @property
    def conda_env_name(self):
        if self.name:
            cwd = pathlib.Path.cwd()
            conda_env_root_b64 = footing.utils.b64_encode(self.conda_env_root)
            return f"{cwd.parent.name}-{self.name}-{conda_env_root_b64}"
        else:
            return self.ref.hash

    @property
    def conda_env_path(self):
        return pathlib.Path(self.conda_env_root) / self.conda_env_name

    @property
    def cache_key(self):
        return self.conda_env_name

    def exe(self, exe):
        """Retrieve the path of an executable in this toolkit"""
        return pathlib.Path(self.conda_env_root) / self.conda_env_name / "bin" / exe

    def build(self):
        """Create a conda env with the tools installed"""
        with self.cache_ref():
            old_cache_obj = self.cache_read(CachedBuild)
            new_cache_obj = CachedBuild(path=str(self.conda_env_path), hash=self.ref.hash)
            if old_cache_obj == new_cache_obj:
                return

            footing.utils.pprint(f"Building toolkit {self.conda_env_name}", color="green")

            # Run pre-install hooks. Reset the ref since hooks can change the hash
            # and the env path
            for func in self.pre_install_hooks:
                func.run()
                self.uncache_ref()

            # Create the env and run installers
            footing.utils.conda_cmd(f"create -q -y -p {self.conda_env_path}")

            for installer in self.installers:
                installer.run(toolkit=self.conda_env_path)

            self.cache_write(new_cache_obj)

            # TODO: Warn when the hash has changed midway. This indicates an improper setup
