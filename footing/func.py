import dataclasses
import pathlib
import typing

import footing.obj
import footing.utils


@dataclasses.dataclass
class Condition:
    pass


@dataclasses.dataclass
class FilesChanged(Condition):
    files: typing.List[footing.obj.File]


@dataclasses.dataclass
class Cmd:
    pass


@dataclasses.dataclass
class Join:
    """Join a command relative to a toolkit"""

    toolkit: "footing.toolkit.Toolkit"
    cmd: str

    def __str__(self):
        self.toolkit.build()
        return f"{self.toolkit.conda_env_path}/bin/{self.cmd}"


@dataclasses.dataclass
class Func(footing.obj.Obj):
    cmd: typing.Union[str, Cmd] = None
    condition: FilesChanged = None
    toolkit: "footing.toolkit.Toolkit" = None

    def run(self, *, toolkit=None):
        toolkit = toolkit or self.toolkit

        if isinstance(toolkit, pathlib.Path):
            run_args = f"-p {toolkit}"
        elif hasattr(toolkit, "conda_env_path"):
            toolkit.build()
            run_args = f"-p {toolkit.conda_env_path}"
        else:
            raise ValueError(f"Invalid toolkit - {toolkit}")

        footing.utils.pprint(self.cmd, color="green")
        return footing.utils.conda_cmd(f"run {run_args} {self.cmd}")
