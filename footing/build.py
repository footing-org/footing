import dataclasses
import pathlib


@dataclasses.dataclass
class Build:
    name: str
    kind: str
    ref: str
    path: pathlib.Path

    def __post_init__(self):
        self.path = pathlib.Path(self.path)

    @classmethod
    def from_def(cls, build):
        return cls(**build)
