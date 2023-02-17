import contextlib
import dataclasses
import os
import pathlib
import typing

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
class Toolkit(footing.core.Task):
    conda_env_root: str = None
    platform: str = None
    editable: bool = False

    def __post_init__(self):
        self.conda_env_root = self.conda_env_root or str(footing.utils.cache_path() / "toolkit")
        self.platform = self.platform or footing.utils.detect_platform()
        self.ctx += [footing.core.Lazy(self.enter)]

        # TODO: Set the project path in the runtime context so that we can re-used toolkits for the same
        # projects in different directories
        self.project = str(pathlib.Path.cwd())

        # For now, every toolkit is duplicated for each project path. In the future we will be able to
        # globally share toolkits when only standard installers (e.g. conda) are used. When non-standard
        # ones are used (e.g. poetry), we must resort to namespacing it to avoid global clashes.
        self._conda_env_name = f"{self.config_name or footing.utils.hash128(self)}-{footing.utils.hash32(self.project)}"

        # TODO: Find a better way to shorten environment names
        if len(str(self.conda_env_path)) > 113:
            raise RuntimeError(
                f"The installation path of this toolkit ({self.conda_env_path}) is too long ({len(self.conda_env_path)} > 113)."
                " Try shortening your toolkit name."
            )

        artifact = footing.core.Path(str(self.conda_env_path))
        self.output += [artifact]
        self.cmd = [
            footing.core.Task(cmd=[footing.core.Lazy(self._create_conda_env)], output=[artifact])
        ] + self.cmd

        super().__post_init__()

    @property
    def conda_env_name(self):
        return self._conda_env_name

    @property
    def conda_env_path(self):
        return pathlib.Path(self.conda_env_root) / self.conda_env_name

    @contextlib.contextmanager
    def enter(self):
        # TODO: Allow users to set isolation levels on the PATH
        prefix = self.conda_env_path
        with footing.ctx.set(
            env={
                "PATH": f"{prefix / 'bin'}:{os.environ.get('PATH', '')}",
                "CONDA_PREFIX": str(prefix),
                "CONDA_DEFAULT_ENV": str(prefix.name),
            }
        ):
            yield

    def _create_conda_env(self):
        """Ran as a dependency"""
        footing.utils.conda_cmd(f"create -q -y -p {self.conda_env_path}")


@dataclasses.dataclass(kw_only=True)
class Bin(footing.core.Task):
    toolkit: str = Toolkit

    def __post_init__(self):
        self.deps += [self.toolkit]
        if self.cmd:
            self.cmd = [footing.core.Lazy(self.bin_cmd, [cmd]) for cmd in self.cmd]
        else:
            self.cmd += [footing.core.Lazy(self.bin_ls)]

        super().__post_init__()

    def bin_cmd(self, cmd):
        return footing.core.Cmd(self.toolkit.conda_env_path / "bin" / cmd)

    def bin_ls(self):
        return footing.core.Cmd(f"ls {self.toolkit.conda_env_path / 'bin'}")
