import dataclasses
import functools
import pathlib
import re
import tempfile
import typing

import orjson

import footing.core
import footing.ext
import footing.utils


@functools.cache
def rsync_bin():
    return footing.ext.bin("rsync")


@functools.cache
def kubectl_bin():
    return footing.ext.bin("kubectl", package="kubernetes-client")


@functools.cache
def git_bin():
    return footing.ext.bin("git")


def asdict(obj):
    """Dumps k8s dictionaries, which have camelcase keys"""

    def snake_to_camel(val):
        components = val.split("_")
        return components[0] + "".join(x.title() for x in components[1:])

    def dict_factory(vals):
        return {snake_to_camel(key): val for key, val in vals if val is not None}

    return dataclasses.asdict(obj, dict_factory=dict_factory)


def fmt_resource_name(name):
    return re.sub("[^0-9a-zA-Z\-]+", "-", name).lower()


@dataclasses.dataclass
class SecretKeyRef:
    name: str
    key: str
    optional: bool = False


@dataclasses.dataclass
class ValueFrom:
    secret_key_ref: SecretKeyRef


@dataclasses.dataclass
class Env:
    name: str
    value: str = None
    value_from: ValueFrom = None

    def __post_init__(self):
        assert self.value or self.value_from


@dataclasses.dataclass
class Port:
    container_port: int


@dataclasses.dataclass
class Service:
    image: str
    name: str = None
    env: typing.List[Env] = dataclasses.field(default_factory=list)
    ports: typing.List[Port] = dataclasses.field(default_factory=list)
    image_pull_policy: str = None
    command: typing.List[str] = None
    args: typing.List[str] = None

    def __post_init__(self):
        self.name = self.name or fmt_resource_name(self.image)


@dataclasses.dataclass
class Sleepy(Service):
    def __post_init__(self):
        self.command = self.command or ["/bin/bash", "-c", "--"]
        self.args = self.args or ["trap : TERM INT; sleep infinity & wait"]

        super().__post_init__()


@dataclasses.dataclass
class Pod(footing.core.Task):
    services: typing.List[Service] = dataclasses.field(default_factory=list)
    spec: typing.Union[str, dict] = None

    def __post_init__(self):
        self.cmd += [footing.core.Callable(self.create)]

        if not self.spec or isinstance(self.spec, dict):
            spec = self.spec or {
                "apiVersion": "v1",
                "kind": "Pod",
                "metadata": {"name": self.resource_name},
                "spec": {"containers": [asdict(container) for container in self.containers]},
            }
            self.spec = orjson.dumps(spec).decode("utf-8")

        super().__post_init__()

    ###
    # Core properties and extensions
    ###

    @property
    def containers(self):
        return self.services

    def _fmt_resource_name(self, name):
        name = fmt_resource_name(name)
        hash = footing.utils.hash32(f"{name}-{self.containers}")
        max_name_len = 253 - (len(hash) + 1)
        return f"{name[:max_name_len]}-{hash}"

    @property
    def resource_name(self):
        return self._resource_name

    @functools.cached_property
    def _resource_name(self):
        return self._fmt_resource_name(self.config_name or "pod")

    ###
    # Core methods and properties
    ###

    def create(self):
        footing.cli.pprint("creating pod")
        with tempfile.TemporaryDirectory() as tmp_d:
            pod_yml_path = pathlib.Path(tmp_d) / "pod.json"
            with open(pod_yml_path, "w") as f:
                f.write(self.spec)

            footing.utils.run(f"{kubectl_bin()} apply -f {pod_yml_path}")

        footing.cli.pprint("waiting for pod")
        footing.utils.run(
            f"{kubectl_bin()} wait --for=condition=ready --timeout '-1s' pod {self.resource_name}"
        )


def default_runner_service():
    return Sleepy(
        image="footingorg/runner:latest",
        name="runner",
        image_pull_policy="Always",
    )


@dataclasses.dataclass
class Runner(Pod):
    def __post_init__(self):
        self._runner = default_runner_service()
        self.services.append(self._runner)

        super().__post_init__()
