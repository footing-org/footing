import dataclasses
import functools
import os
import pathlib
import re
import subprocess
import tempfile
import textwrap
import typing

import xxhash

import footing.ext
import footing.obj
import footing.utils


def asdict(obj):
    """Dumps k8s dictionaries, which have camelcase keys"""

    def snake_to_camel(val):
        components = val.split("_")
        return components[0] + "".join(x.title() for x in components[1:])

    def dict_factory(vals):
        return {snake_to_camel(key): val for key, val in vals}

    return dataclasses.asdict(obj, dict_factory=dict_factory)


@dataclasses.dataclass
class Env:
    name: str
    value: str


@dataclasses.dataclass
class Port:
    container_port: int


@dataclasses.dataclass
class Service:
    image: str
    name: str
    env: typing.List[Env] = dataclasses.field(default_factory=list)
    ports: typing.List[Port] = dataclasses.field(default_factory=list)
    image_pull_policy: str = None
    command: typing.List[str] = None
    args: typing.List[str] = None


def default_runner_service():
    return Service(
        image="wesleykendall/footing:latest",
        name="runner",
        image_pull_policy="Always",
        command=["/bin/bash", "-c", "--"],
        args=["trap : TERM INT; sleep infinity & wait"],
    )


@dataclasses.dataclass
class Runner:
    service: Service = dataclasses.field(default_factory=default_runner_service)
    env: typing.List[Env] = dataclasses.field(default_factory=list)

    def __post_init__(self):
        self.service.env = self.service.env + self.env

    @property
    def resource_name(self):
        return self.service.name

    def local_exec_cmd(self, exe, args, pod):
        return ""

    def remote_exec_cmd(self, exe, args, pod):
        # TODO: properly escape args
        return f"footing {exe} {' '.join(args)}"


@dataclasses.dataclass
class GitRunner(Runner, footing.obj.Lazy):
    repo: str = None
    branch: str = None

    def render(self):
        """Lazily compute properties

        Put repo and branch as public properties so that they are part of the hash.
        We leave them off the dataclass here since the K8s pod definition will
        be invalid
        """
        if not self.repo:
            out = footing.utils.run(
                f"{self.git_bin} config --get remote.origin.url", stdout=subprocess.PIPE
            )
            url = out.stdout.decode("utf-8")

            if url.startswith("git@github.com"):
                repo = url.strip().split(":", 1)[1][:-4]
                self.repo = f"https://github.com/{repo}"
            elif url.startswith("https://github.com"):
                self.repo = url
            else:
                raise ValueError(f'Invalid git remote repo URL - "{url}"')

        if not self.branch:
            out = footing.utils.run(
                f"{self.git_bin} rev-parse --abbrev-ref HEAD", stdout=subprocess.PIPE
            )
            self.branch = out.stdout.decode("utf-8").strip()

    ###
    # Core properties and extensions
    ###

    @property
    def resource_name(self):
        return f"{self.repo.split('/')[-1]}-{self.branch}".replace("_", "-")

    @property
    def git_bin(self):
        return self._git_bin

    @functools.cached_property
    def _git_bin(self):
        return footing.ext.bin("git")

    ###
    # Core methods and properties
    ###

    def remote_exec_cmd(self, exe, args, pod):
        clone_cmd = (
            f"git clone {self.repo} --branch {self.branch} --single-branch /project 2> /dev/null"
        )
        pull_cmd = f"git -C /project reset --hard > /dev/null && git -C /project pull > /dev/null"
        return f"(({clone_cmd}) || ({pull_cmd})) && {super().remote_exec_cmd(exe, args, pod)}"


@dataclasses.dataclass
class RSyncRunner(Runner, footing.obj.Lazy):
    hostname: str = None

    def render(self):
        """Lazily compute properties

        Put the hostname as a public property so that it's are part of the hash.
        We leave them off the dataclass here since the K8s pod definition will
        be invalid
        """
        if not self.hostname:
            out = footing.utils.run(f"hostname", stdout=subprocess.PIPE)
            self.hostname = out.stdout.decode("utf-8").strip()

    ###
    # Core properties and extensions
    ###

    @property
    def resource_name(self):
        return re.sub("[^0-9a-zA-Z\-]+", "-", self.hostname)

    @property
    def rsync_bin(self):
        return self._rsync_bin

    @functools.cached_property
    def _rsync_bin(self):
        return footing.ext.bin("rsync")

    @property
    def kubectl_bin(self):
        return self._kubectl_bin

    @functools.cached_property
    def _kubectl_bin(self):
        return footing.ext.bin("kubectl", package="kubernetes")

    ###
    # Core methods and properties
    ###

    def local_exec_cmd(self, exe, args, pod):
        rsync_bin = self.rsync_bin
        kubectl_bin = self.kubectl_bin

        rsync_flags = '-aur --blocking-io --include="**.gitignore" --exclude="/.git" --filter=":- .gitignore" --delete-after --rsync-path='
        rsh = f'--rsh="{kubectl_bin} exec -c {self.service.name} {pod.resource_name} -i -- "'

        return f"{rsync_bin} {rsync_flags} {rsh} . rsync:/project"


@dataclasses.dataclass
class Cluster(footing.obj.Obj):
    context: str

    @property
    def entry(self):
        return super().entry | {
            "/": footing.obj.Entry(method=self.exec),
        }

    def build(self):
        pass


@dataclasses.dataclass
class Pod(footing.obj.Obj):
    runner: Runner = dataclasses.field(default_factory=Runner)
    spec: str = None
    services: typing.List[Service] = dataclasses.field(default_factory=list)

    def render(self):
        """Lazy properties"""
        spec = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": self.resource_name},
            "spec": {
                "containers": [asdict(self.runner.service)]
                + [asdict(service) for service in self.services]
            },
        }
        yaml = footing.ext.mod("yaml", package="pyyaml")
        self.spec = yaml.dump(spec)

    ###
    # Core properties and extensions
    ###

    @property
    def entry(self):
        return super().entry | {
            "build": footing.obj.Entry(method=self.build),
            "delete": footing.obj.Entry(method=self.delete),
            "/": footing.obj.Entry(method=self.exec),
        }

    @property
    def resource_name(self):
        return self._resource_name

    @functools.cached_property
    def _resource_name(self):
        name = (self.name or "pod").replace("_", "-")
        name += f"-{self.runner.resource_name}"

        # TODO: Might have to consider a better hashing strategy based on how
        # a shared cluster is used
        hash = xxhash.xxh32_hexdigest(f"{name}-{self.runner}")
        max_name_len = 253 - (len(hash) + 1)
        return f"{name[:max_name_len]}-{hash}".lower()

    @property
    def kubectl_bin(self):
        return self._kubectl_bin

    @functools.cached_property
    def _kubectl_bin(self):
        return footing.ext.bin("kubectl", package="kubernetes")

    ###
    # Core methods and properties
    ###

    def exec(self, exe, args, retry=True):
        """Exec a function in this pod"""
        self.build()

        try:
            if not exe:
                for name in footing.config.registry():
                    footing.cli.pprint(name, weight=None, icon=False)
            else:
                # git is in the PATH of the container, so no need to provide an absolute path
                footing.cli.pprint("provisioning")
                local_cmd = self.runner.local_exec_cmd(exe, args, self)
                remote_cmd = self.runner.remote_exec_cmd(exe, args, self)

                footing.utils.run(
                    f"bash -c '{local_cmd}' && "
                    f"{self.kubectl_bin} exec --stdin --tty -c {self.runner.service.name} {self.resource_name} -- bash -c '{remote_cmd}'",
                    stderr=subprocess.PIPE,
                )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8").strip() if exc.stderr else ""
            if (
                retry
                and stderr
                == f'Error from server (NotFound): pods "{self.resource_name}" not found'
            ):
                footing.cli.pprint("Pod not found. Rebuilding and retrying.", color="red")
                self.build(cache=False)
                return self.exec(exe, args, retry=False)
            else:
                raise

    def build(self, cache=True):
        if self.is_cached and cache:
            return

        footing.cli.pprint("creating pod")
        with tempfile.TemporaryDirectory() as tmp_d:
            pod_yml_path = pathlib.Path(tmp_d) / "pod.yml"
            with open(pod_yml_path, "w") as f:
                f.write(self.spec)

            footing.utils.run(f"{self.kubectl_bin} apply -f {pod_yml_path}")

        footing.cli.pprint("waiting for pod")
        footing.utils.run(
            f"{self.kubectl_bin} wait --for=condition=ready --timeout '-1s' pod {self.resource_name}"
        )

        self.write_cache()

    def delete(self):
        self.delete_cache()

        try:
            footing.utils.run(
                f"{self.kubectl_bin} delete pod {self.resource_name}", stderr=subprocess.PIPE
            )
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8").strip() if exc.stderr else ""
            if stderr == f'Error from server (NotFound): pods "{self.resource_name}" not found':
                pass
            else:
                raise
