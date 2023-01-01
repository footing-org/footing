import contextlib
import dataclasses
import pathlib
import shutil
import tempfile
import typing
import unittest.mock

import conda_lock.conda_lock
from conda_lock.src_parser import environment_yaml, pyproject_toml, LockSpecification

import footing.util


@dataclasses.dataclass
class Toolset:
    manager: str
    tools: list = dataclasses.field(default_factory=list)
    file: str = None

    def __post_init__(self):
        if self.manager not in ["conda", "pip"]:
            raise ValueError(f"Unsupported manager '{self.manager}'")

        if not self.tools and not self.file:
            raise ValueError("Must provide a list of tools or a file for toolkit")

        if self.file and self.file not in (
            "pyproject.toml",
            "environment.yaml",
            "environment.yml",
        ):
            raise ValueError(f"Unsupported file '{self.file}'")

    @property
    def dependency_spec(self):
        """Generate the dependency specification"""
        if self.file == "pyproject.toml":
            # For now, assume users aren't using conda-lock and ensure pyproject
            # requirements are always installed with pip.
            # TODO: Detect if using conda-lock and let conda-lock do its
            # pip->conda translation magic

            with unittest.mock.patch(
                "conda_lock.src_parser.pyproject_toml.normalize_pypi_name",
                side_effect=lambda name: name,
            ):
                spec = pyproject_toml.parse_pyproject_toml(pathlib.Path(self.file))
        elif self.file in ("environment.yaml", "environment.yml"):
            spec = environment_yaml.parse_environment_file(pathlib.Path(self.file))
        else:
            spec = LockSpecification(
                channels=[],
                dependencies=[
                    pyproject_toml.parse_python_requirement(
                        tool,
                        manager=self.manager,
                        normalize_name=False,
                    )
                    for tool in self.tools
                ],
                platforms=[],
                sources=[],
            )

        for dep in spec.dependencies:
            dep.name = dep.name.lower().strip()
            dep.manager = self.manager if dep.name not in ("python", "pip") else "conda"

            if not spec.channels and dep.manager == "conda":
                dep.conda_channel = dep.conda_channel or "conda-forge"

        spec.sources = []
        return spec

    @classmethod
    def from_def(cls, toolset):
        return cls(
            tools=toolset.get("tools", []),
            manager=toolset["manager"],
            file=toolset.get("file"),
        )


@dataclasses.dataclass
class Toolkit:
    key: str
    toolsets: typing.List[Toolset] = dataclasses.field(default_factory=list)
    base: typing.Optional["Toolkit"] = None
    platforms: typing.List[str] = dataclasses.field(default_factory=list)

    def __post_init__(self):
        self.platforms = self.platforms or ["osx-arm64", "osx-64", "linux-64"]

    @property
    def uri(self):
        return f"toolkit:{self.key}"

    @property
    def conda_env_name(self):
        """The conda environment name"""
        config = footing.util.local_config()
        name = config["project"]["key"]

        if self.key != "default":
            name += f"-{self.key}"

        return name

    @property
    def flattened_toolsets(self):
        """Generate a flattened list of all toolsets"""
        toolsets = []
        if self.base:
            toolsets.extend(self.base.flattened_toolsets)

        toolsets.extend(self.toolsets)

        return toolsets

    @property
    def dependency_specs(self):
        """Return dependency specs from all toolsets"""
        return [toolset.dependency_spec for toolset in self.flattened_toolsets]

    @classmethod
    def from_def(cls, toolkit):
        toolsets = []
        if toolkit.get("toolsets"):
            toolsets.extend([Toolset.from_def(toolset) for toolset in toolkit["toolsets"]])
        else:
            toolsets.extend([Toolset.from_def(toolkit)])

        return cls(
            key=toolkit["key"],
            toolsets=toolsets,
            base=Toolkit.from_key(toolkit["base"]) if toolkit.get("base") else None,
        )

    @classmethod
    def from_key(cls, key):
        config = footing.util.local_config()

        for toolkit in config["toolkits"]:
            if toolkit["key"] == key:
                return cls.from_def(toolkit)

    @classmethod
    def from_default(cls):
        config = footing.util.local_config()
        num_public_toolkits = 0

        key = None
        for toolkit in config["toolkits"]:
            if toolkit["key"] == "default":
                key = "default"
                break
            elif not toolkit["key"].startswith("_"):
                key = toolkit["key"]
                num_public_toolkits += 1
        else:
            if num_public_toolkits != 1:
                return None

        return cls.from_key(key)

    @property
    def lock_file(self):
        return footing.util.locks_dir() / f"{self.uri}.yml"

    def lock(self):
        def _parse_source_files(*args, **kwargs):
            return self.dependency_specs

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch(
                    "conda_lock.conda_lock.parse_source_files",
                    side_effect=_parse_source_files
                )
            )
            stack.enter_context(unittest.mock.patch("sys.exit"))

            # Retrieve the lookup table since it's patched
            pyproject_toml.get_lookup()

            # Run the actual locking function
            footing.util.locks_dir().mkdir(exist_ok=True, parents=True)
            lock_args = [
                "--lockfile",
                str(self.lock_file),
                "--mamba",
                "--strip-auth",
                "--conda",
                str(footing.util.condabin_dir() / "mamba"),
            ]
            for platform in self.platforms:
                lock_args.extend(["-p", platform])

            conda_lock.conda_lock.lock(lock_args)

    def sync(self):
        self.lock()

        with contextlib.ExitStack() as stack:
            stack.enter_context(unittest.mock.patch("sys.exit"))
            tmpdir = stack.enter_context(tempfile.TemporaryDirectory())
            tmp_lock_file = pathlib.Path(tmpdir) / "conda-lock.yml"
            shutil.copy(str(self.lock_file), str(tmp_lock_file))
            conda_lock.conda_lock.install(["--name", str(self.key), str(tmp_lock_file)])


def get(key=None):
    if key:
        return Toolkit.from_key(key)
    else:
        return Toolkit.from_default()


def ls(active=False):
    config = footing.util.local_config()

    if active:
        key = footing.settings.get("toolkit")
        if key:
            return [Toolkit.from_key(key)]
        else:
            return []
    else:
        return [
            Toolkit.from_def(toolkit)
            for toolkit in config["toolkits"]
            if not toolkit["key"].startswith("_")
        ]
