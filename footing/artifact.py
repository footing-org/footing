import dataclasses

import conda_pack

import footing.toolkit
import footing.util


@dataclasses.dataclass
class Artifact:
    name: str
    kind: str
    ref: str
    toolkit: footing.toolkit.Toolkit = None
    _def: dict = None

    @property
    def key(self):
        return f"{self.kind}:{self.name}"

    @classmethod
    def from_def(cls, artifact):
        toolkit = footing.toolkit.get(artifact["toolkit"])

        return cls(key=artifact["key"], kind=artifact["kind"], toolkit=toolkit, _def=toolkit)

    @classmethod
    def from_key(cls, key):
        config = footing.util.local_config()

        for artifact in config["artifacts"]:
            if artifact["key"] == key:
                return cls.from_def(artifact)

    def build(self):
        artifacts_dir = footing.util.artifacts_dir()
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        if self.kind == "squashfs":
            output_file = artifacts_dir / f"{self.key}.squashfs"
            conda_pack.pack(
                name=self.toolkit.conda_env_name,
                output=str(output_file),
                ignore_missing_files=True,
            )

        else:
            raise ValueError(f"Invalid kind - '{self.kind}'")


def get(key):
    return Artifact.from_key(key)
