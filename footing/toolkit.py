import contextlib
import copy
import dataclasses
import hashlib
import pathlib
import tempfile
import typing
import unittest.mock

import conda_lock.conda_lock
from conda_lock.src_parser import environment_yaml, LockSpecification, pyproject_toml
import yaml

import footing.build
import footing.registry
import footing.util


@dataclasses.dataclass
class Toolset:
    manager: str
    tools: list = dataclasses.field(default_factory=list)
    file: str = None

    def __post_init__(self):
        if self.manager not in ["conda", "pip"]:
            raise ValueError(f"Unsupported manager '{self.manager}'")

        #if not self.tools and not self.file:
        #    raise ValueError("Must provide a list of tools or a file for toolkit")

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
    name: str
    toolsets: typing.List[Toolset] = dataclasses.field(default_factory=list)
    base: typing.Optional["Toolkit"] = None
    platforms: typing.List[str] = dataclasses.field(default_factory=list)
    category: str = "dev"
    _def: dict = None

    @property
    def uri(self):
        return f"toolkit:{self.name}"

    def __post_init__(self):
        self.platforms = self.platforms or [
            "osx-arm64",
            "linux-aarch64",
        ]  # , "osx-64", "linux-64"]

    @property
    def ref(self):
        definitions = [
            yaml.dump(toolkit._def, Dumper=yaml.SafeDumper) for toolkit in self.flattened_toolkits
        ]
        files = [toolset.file for toolset in self.flattened_toolsets if toolset.file]

        h = hashlib.sha256()
        for platform in self.platforms:
            h.update(platform.encode("utf-8"))

        for definition in definitions:
            h.update(definition.encode("utf-8"))

        for file in files:
            with open(file, "rb") as f:
                h.update(f.read())

        return h.hexdigest()

    @property
    def conda_env_name(self):
        """The conda environment name"""
        config = footing.util.local_config()
        name = config["project"]["name"]

        if self.name != "default":
            name += f"-{self.name}"

        return name

    @property
    def flattened_toolkits(self):
        """Generate a flattened list of all toolkits"""
        toolkits = []
        if self.base:
            toolkits.extend(self.base.flattened_toolkits)

        toolkits.extend([self])

        return toolkits

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
        specs = [toolset.dependency_spec for toolset in self.flattened_toolsets]
        dependencies = (dependency for spec in specs for dependency in spec.dependencies)

        python_dep = pip_dep = None
        has_pip_dependencies = False
        for dependency in dependencies:
            if dependency.name == "python":
                python_dep = dependency
            elif dependency.name == "pip":
                pip_dep = dependency

            if dependency.manager == "pip":
                has_pip_dependencies = True

        # If python exists and we have pip dependencies without pip, install pip
        if python_dep and not pip_dep and has_pip_dependencies:
            pip_dep = copy.deepcopy(python_dep)
            pip_dep.name = "pip"
            pip_dep.version = "22.3.1"

            specs.extend(
                [LockSpecification(channels=[], dependencies=[pip_dep], platforms=[], sources=[])]
            )

        return specs

    @classmethod
    def from_def(cls, toolkit):
        toolsets = []
        if toolkit.get("toolsets"):
            toolsets.extend([Toolset.from_def(toolset) for toolset in toolkit["toolsets"]])
        else:
            toolsets.extend([Toolset.from_def(toolkit)])

        return cls(
            name=toolkit["name"],
            category=toolkit.get("category", "dev"),
            toolsets=toolsets,
            base=Toolkit.from_name(toolkit["base"]) if toolkit.get("base") else None,
            _def=toolkit,
        )

    @classmethod
    def from_name(cls, name):
        config = footing.util.local_config()

        for toolkit in config["toolkits"]:
            if toolkit["name"] == name:
                return cls.from_def(toolkit)

    @classmethod
    def from_default(cls):
        config = footing.util.local_config()
        num_public_toolkits = 0

        name = None
        for toolkit in config["toolkits"]:
            if toolkit["name"] == "default":
                name = "default"
                break
            elif not toolkit["name"].startswith("_"):
                name = toolkit["name"]
                num_public_toolkits += 1
        else:
            if num_public_toolkits != 1:
                return None

        return cls.from_name(name)

    def lock(self, output_path):
        def _parse_source_files(*args, **kwargs):
            return self.dependency_specs

        with contextlib.ExitStack() as stack:
            stack.enter_context(
                unittest.mock.patch(
                    "conda_lock.conda_lock.parse_source_files", side_effect=_parse_source_files
                )
            )
            stack.enter_context(unittest.mock.patch("sys.exit"))

            # Retrieve the lookup table since it's patched
            pyproject_toml.get_lookup()

            # Run the actual locking function
            lock_args = [
                "--lockfile",
                str(output_path),
                "--mamba",
                "--strip-auth",
                "--conda",
                str(footing.util.condabin_dir() / "mamba"),
            ]
            for platform in self.platforms:
                lock_args.extend(["-p", platform])

            conda_lock.conda_lock.lock(lock_args)

    def install(self):
        local_registry = footing.registry.local()
        repo_registry = footing.registry.repo()
        build_kwargs = {"ref": self.ref, "name": self.name}

        lock_build_kwargs = {"kind": "toolkit-lock", **build_kwargs}
        lock_package = repo_registry.find(**lock_build_kwargs)
        if not lock_package:
            local_lock_package = local_registry.find(**lock_build_kwargs)
            if local_lock_package:
                # Handle the case where a local lock file might be avaiable
                with tempfile.NamedTemporaryFile() as tmp_file:
                    local_lock_build = local_lock_package.pull(tmp_file.name)
                    lock_package = repo_registry.push(local_lock_build)
            else:
                # TODO: Refactor this into build system
                with tempfile.TemporaryDirectory() as tmp_dir:
                    lock_file_path = pathlib.Path(tmp_dir) / "conda-lock.yml"
                    # We need to re-compute the lock
                    self.lock(lock_file_path)
                    lock_build = footing.build.Build(path=lock_file_path, **lock_build_kwargs)
                    local_registry.push(lock_build)
                    lock_package = repo_registry.push(lock_build)

        toolkit_build_kwargs = {"kind": "toolkit", **build_kwargs}
        toolkit_package = local_registry.find(**toolkit_build_kwargs)
        if not toolkit_package:
            # TODO: Refactor this into build system
            with contextlib.ExitStack() as stack:
                stack.enter_context(unittest.mock.patch("sys.exit"))
                tmp_dir = stack.enter_context(tempfile.TemporaryDirectory())
                tmp_lock_file = pathlib.Path(tmp_dir) / "conda-lock.yml"
                # TODO: We assume the lock build's URI is a file path that can be directly opened.
                # This assumption is safe to make with filesystem registries, but we should
                # abstract this under the Build class
                lock_package.pull(tmp_lock_file)
                install_args = ["--name", self.conda_env_name, str(tmp_lock_file)]
                if self.category != "dev":
                    install_args.extend(["--no-dev"])

                conda_lock.conda_lock.install(install_args)
                if self.category == "dev":
                    footing.util.conda_run("pip install -e .", toolkit=self)

            toolkit_package = local_registry.push(
                footing.build.Build(
                    path=(footing.util.conda_dir() / "envs" / self.conda_env_name).resolve(),
                    **toolkit_build_kwargs,
                ),
                copy=False,
            )

        return toolkit_package


def get(name=None):
    if name:
        return Toolkit.from_name(name)
    else:
        return Toolkit.from_default()


def ls(active=False):
    config = footing.util.local_config()

    if active:
        name = footing.settings.get("toolkit")
        if name:
            return [Toolkit.from_name(name)]
        else:
            return []
    else:
        return [
            Toolkit.from_def(toolkit)
            for toolkit in config["toolkits"]
            if not toolkit["name"].startswith("_")
        ]
