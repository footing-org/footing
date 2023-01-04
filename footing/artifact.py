import dataclasses
import hashlib
import pathlib
import tempfile
import textwrap

import conda_pack
import dirhash
import docker
import yaml

import footing.registry
import footing.toolkit
import footing.util


def build_packed_toolkit(artifact):
    local_registry = footing.registry.local()
    suffix = artifact.kind if artifact.kind != "packed-toolkit" else "tar.gz"

    with tempfile.TemporaryDirectory() as tmp_dir:
        output_path = pathlib.Path(tmp_dir) / f"{artifact.uri}.{suffix}"
        conda_pack.pack(
            name=artifact.toolkit.conda_env_name,
            output=str(output_path),
            ignore_missing_files=True,
            filters=[("exclude", "*__pycache__*")],
        )

        return local_registry.push(
            footing.build.Build(
                ref=artifact.ref, name=artifact.name, kind=artifact.kind, path=output_path
            )
        )


def build_image(artifact):
    local_registry = footing.registry.local()

    with tempfile.TemporaryDirectory() as tmp_dir:
        docker_file_path = pathlib.Path(tmp_dir) / "Dockerfile"
        with docker_file_path.open("w") as docker_file:
            entry = ""
            if artifact.entry:
                entry = (
                    "ENTRYPOINT ["
                    + ", ".join([f'"{val}"' for val in artifact.entry.split()])
                    + "]"
                )

            docker_file.write(
                textwrap.dedent(
                    f"""
                    FROM wesleykendall/footing AS builder

                    COPY . /project
                    WORKDIR /project

                    RUN footing toolkit install {artifact.toolkit.name}
                    RUN conda-pack \
                        --name {artifact.toolkit.conda_env_name} \
                        --output /tmp/packed.tar.gz \
                        --ignore-missing-files \
                        --exclude "*__pycache__*"

                    RUN mkdir /env

                    RUN tar -xzf /tmp/packed.tar.gz -C /env

                    SHELL ["/bin/bash", "-c"]
                    RUN /env/bin/conda-unpack

                    FROM alpine
                    RUN apk add gcompat
                    ENV PATH=/env/bin:$PATH
                    WORKDIR /code
                    COPY {artifact.code} /code
                    COPY --from=builder /env /env
                    {entry}
                    """
                )
            )

        with docker_file_path.open("rb") as docker_file:
            client = docker.from_env()
            image, _ = client.images.build(path=".", dockerfile=docker_file_path)

        return local_registry.push(
            footing.build.Build(
                ref=artifact.ref, name=artifact.name, kind=artifact.kind, path=str(image.id)
            ),
            copy=False,
        )


def build_sphinx(artifact):
    local_registry = footing.registry.local()

    with footing.util.cd("docs"):
        footing.util.shell("make html")

    return local_registry.push(
        footing.build.Build(
            ref=artifact.ref,
            name=artifact.name,
            kind=artifact.kind,
            path=pathlib.Path("docs/_build/html").resolve(),
        ),
        copy=False,
    )


@dataclasses.dataclass
class Artifact:
    name: str
    kind: str
    toolkit: footing.toolkit.Toolkit = None
    code: str = "."
    entry: str = None
    _def: dict = None

    @property
    def uri(self):
        return f"{self.kind}:{self.name}"

    @classmethod
    def from_def(cls, artifact):
        kwargs = {
            **artifact,
            **{
                "toolkit": footing.toolkit.get(artifact["toolkit"])
                if artifact.get("toolkit")
                else None,
                "_def": artifact,
            },
        }

        return cls(**kwargs)

    @classmethod
    def from_name(cls, name):
        # TODO: Refactor this to no longer use "name" and use URIs
        config = footing.util.local_config()

        for artifact in config["artifacts"]:
            if artifact["name"] == name:
                return cls.from_def(artifact)

    @property
    def ref(self):
        definition = yaml.dump(self._def, Dumper=yaml.SafeDumper)

        h = hashlib.sha256()
        h.update(definition.encode("utf-8"))

        if self.code:
            h.update(dirhash.dirhash(self.code, "sha256").encode("utf-8"))

        if self.entry:
            h.update(self.entry.encode("utf-8"))

        if self.toolkit:
            h.update(self.toolkit.ref.encode("utf-8"))

        return h.hexdigest()

    @property
    def package(self):
        local_registry = footing.registry.local()
        return local_registry.find(kind=self.kind, name=self.name, ref=self.ref)

    def build(self):
        package = self.package
        if not package:
            if self.toolkit:
                # TODO: Force re-install in the case someone modified the toolkit locally
                self.toolkit.install()

            if self.kind in ("squashfs", "packed-toolkit"):
                package = build_packed_toolkit(self)
            elif self.kind == "image":
                package = build_image(self)
            elif self.kind == "sphinx":
                package = build_sphinx(self)
            else:
                raise ValueError(f"Invalid kind - '{self.kind}'")

        return package


def get(name):
    # TODO: Change this function to look up on URI
    return Artifact.from_name(name)


def ls(registry=None, name=None):
    config = footing.util.local_config()

    return [
        Artifact.from_def(artifact)
        for artifact in config["artifacts"]
        if name is None or artifact["name"] == name
    ]
