import dataclasses
import pathlib
import typing

import footing.cli
import footing.obj
import footing.utils


@dataclasses.dataclass
class Condition:
    pass


@dataclasses.dataclass
class FilesChanged(Condition):
    files: typing.List[footing.obj.File]


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
    cmd: str = None
    condition: FilesChanged = None
    toolkit: "footing.toolkit.Toolkit" = None

    @property
    def entry(self):
        return {
            "main": footing.obj.Entry(method=self.run),
        }

    @property
    def rendered(self):
        return str(self.cmd)

    def run(self, *, toolkit=None, cwd=None):
        cmd = self.rendered
        toolkit = toolkit or self.toolkit
        if toolkit:
            if isinstance(toolkit, pathlib.Path):
                prefix = toolkit
            elif hasattr(toolkit, "conda_env_path"):
                toolkit.build()
                prefix = toolkit.conda_env_path
            else:
                raise ValueError(f"Invalid toolkit - {toolkit}")
        else:
            prefix = None

        footing.cli.pprint(cmd.removeprefix(footing.utils.conda_exe() + " "))
        return footing.utils.conda_run(cmd, prefix=prefix)
