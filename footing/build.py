import dataclasses


@dataclasses.dataclass
class Build:
    name: str
    kind: str
    ref: str
    path: str

    @classmethod
    def from_def(cls, build):
        return cls(**build)
