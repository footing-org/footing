import dataclasses
import typing

import footing.util


@dataclasses.dataclass
class Toolset:
    tools: list = dataclasses.field(default_factory=list)
    manager: str = "mamba"
    file: str = None

    def __post_init__(self):
        if self.manager not in ["poetry", "pip", "mamba"]:
            raise ValueError(f"Unsupported manager '{self.manager}'")

    def mamba_sync(self, *, toolkit):
        # TODO: Support environment.yml files
        footing.util.conda_install(" ".join(self.tools) + " -y", toolkit=toolkit)

    def poetry_sync(self, *, toolkit):
        footing.util.conda_run("poetry lock --no-update && poetry install", toolkit=toolkit)

    def pip_sync(self, *, toolkit):
        if self.tools:
            footing.util.conda_run("pip install " + " ".join(self.tools), toolkit=toolkit)
        elif self.file:
            footing.util.conda_run("pip install -r " + self.file)

    def sync(self, *, toolkit):
        """Syncs the toolset"""
        if self.manager == "mamba":
            return self.mamba_sync(toolkit=toolkit)
        if self.manager == "pip":
            return self.pip_sync(toolkit=toolkit)
        if self.manager == "poetry":
            return self.poetry_sync(toolkit=toolkit)
        else:
            raise AssertionError(f"Unsupported manager '{self.manager}'")


@dataclasses.dataclass
class Toolkit:
    key: str
    toolsets: typing.List[Toolset] = dataclasses.field(default_factory=list)
    base: typing.Optional["Toolkit"] = None

    @property
    def conda_env_name(self):
        """The conda environment name"""
        config = footing.util.local_config()
        name = config["project"]["key"]

        if self.key != "default":
            name += f"-{self.key}"

        return name

    def __post_init__(self):
        self.flattened_toolsets = []
        if self.base:
            self.flattened_toolsets.extend(self.base.flattened_toolsets)

        self.flattened_toolsets.extend(self.toolsets)

    @classmethod
    def from_def(cls, toolkit):
        toolsets = []
        if toolkit.get("toolsets"):
            toolsets.extend([Toolset(tools=toolset["tools"]) for toolset in toolkit["toolsets"]])
        else:
            toolsets.extend(
                [
                    Toolset(
                        **{key: val for key, val in toolkit.items() if key in ("manager", "tools")}
                    )
                ]
            )

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

    def sync(self):
        # TODO: Don't re-create the env every time
        footing.util.conda(f"create -n {self.conda_env_name} -y")
        for toolset in self.flattened_toolsets:
            toolset.sync(toolkit=self)


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
