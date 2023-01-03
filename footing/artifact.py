import dataclasses
import hashlib
import pathlib
import tempfile

import conda_pack
import yaml

import footing.registry
import footing.toolkit
import footing.util


def build_squash_fs(artifact):
     with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = pathlib.Path(tmp_dir) / f"{artifact.key}.squashfs"
        conda_pack.pack(
            name=artifact.toolkit.conda_env_name,
            output=str(output_path),
            ignore_missing_files=True,
        )

        return local_registry.push(
            footing.build.Build(
                ref=ref, name=artifact.name, kind=artifact.kind, path=output_path
            )
        )


def build_image(artifact):
    pass


@dataclasses.dataclass
class Artifact:
    name: str
    kind: str
    toolkit: footing.toolkit.Toolkit = None
    _def: dict = None

    @property
    def key(self):
        return f"{self.kind}:{self.name}"

    @classmethod
    def from_def(cls, artifact):
        toolkit = footing.toolkit.get(artifact["toolkit"]) if artifact.get("toolkit") else None

        return cls(name=artifact["name"], kind=artifact["kind"], toolkit=toolkit, _def=artifact)

    @classmethod
    def from_key(cls, key):
        config = footing.util.local_config()

        for artifact in config["artifacts"]:
            if artifact["name"] == key:
                return cls.from_def(artifact)

    @property
    def ref(self):
        definition = yaml.dump(self._def, Dumper=yaml.SafeDumper)

        h = hashlib.sha256()
        h.update(definition.encode("utf-8"))

        if self.toolkit:
            h.update(self.toolkit.ref.encode("utf-8"))

        return h.hexdigest()

    def build(self):
        ref = self.ref
        local_registry = footing.registry.local()
        package = local_registry.find(kind=self.kind, name=self.name, ref=ref)
        if not package:
            if self.toolkit:
                # TODO: Force re-install in the case someone modified the toolkit locally
                self.toolkit.install()

            if self.kind == "squashfs":
                package = build_squash_fs(artifact)
            elif self.kind == "image":
                package = build_image(artifact)
            else:
                raise ValueError(f"Invalid kind - '{self.kind}'")

        return package


def get(key):
    # TODO: Change this function to look up on kind/name
    return Artifact.from_key(key)
