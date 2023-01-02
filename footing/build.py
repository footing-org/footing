import dataclasses
import pathlib

import yaml

import footing.util


@dataclasses.dataclass
class Build:
    uri: str
    ref: str
    path: str

    def __post_init__(self):
        if isinstance(self.path, pathlib.Path):
            self.path = str(self.path.resolve())

    @classmethod
    def from_def(cls, build):
        return cls(**build)


def get(uri, ref=None):
    build_name = uri
    if ref:
        build_name += f":{ref}"

    build_path = footing.util.builds_dir() / f"{build_name}.yml"
    try:
        with open(build_path) as build_file:
            build = yaml.load(build_file, Loader=yaml.SafeLoader)
            return Build.from_def(build)
    except FileNotFoundError:
        return None


def set(uri, build, ref=None):
    build_name = uri
    if ref:
        build_name += f":{ref}"

    footing.util.builds_dir().mkdir(exist_ok=True, parents=True)
    build_path = footing.util.builds_dir() / f"{build_name}.yml"
    with open(build_path, "w") as build_file:
        yaml.dump(dataclasses.asdict(build), build_file, Dumper=yaml.SafeDumper)
