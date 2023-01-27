import dataclasses
import functools
import os
import pathlib
import subprocess
import tempfile
import textwrap
import typing

import xxhash

import footing.obj
import footing.utils


@dataclasses.dataclass
class Env:
    name: str
    value: str


@dataclasses.dataclass
class Service:
    image: str
    name: str
    env: typing.List[Env] = dataclasses.field(default_factory=list)


@dataclasses.dataclass
class Cluster(footing.obj.Obj):
    def build(self):
        pass


@dataclasses.dataclass
class Pod(footing.obj.Obj):
    spec: str = None
    services: typing.List[Service] = dataclasses.field(default_factory=list)

    def lazy_post_init(self):
        """Lazily compute post_init properties"""

        spec = {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": self.resource_name},
            "spec": {
                "containers": [{
                    "name": "runner",
                    "image": "wesleykendall/footing:latest",
                    "imagePullPolicy": "Always", 
                    "command": ["/bin/bash", "-c", "--"],
                    "args": ["trap : TERM INT; sleep infinity & wait"]
                }] + [dataclasses.asdict(service) for service in self.services]
            }
        }
        yaml = self.mod("yaml", package="pyyaml")
        self.spec = yaml.dump(spec)

    ###
    # Core properties and extensions
    ###

    @property
    def entry(self):
        return {
            "build": footing.obj.Entry(method=self.build),
            "delete": footing.obj.Entry(method=self.delete),
            "/": footing.obj.Entry(method=self.exec),
        }

    @property
    def resource_name(self):
        return (self.name or "pod").replace("_", "-")

    @property
    def kubectl_bin(self):
        return self._kubectl_bin

    @functools.cached_property
    def _kubectl_bin(self):
        return self.bin("kubectl", package="kubernetes")

    ###
    # Core methods and properties
    ###

    def kubectl_exec_cmd(self, exe, args):
        return f"footing {exe}"

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
                cmd = self.kubectl_exec_cmd(exe, args)

                footing.utils.run(
                    f"{self.kubectl_bin} exec {self.resource_name} -- bash -c '{cmd}'",
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
        # TODO: Run these methods automatically as part of build process. Do the same
        # for caching
        self.render()

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
        self.render()

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


@dataclasses.dataclass
class GitPod(Pod):
    repo: str = None
    branch: str = None

    def lazy_post_init(self):
        """Lazily compute post_init properties"""
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

        super().lazy_post_init()

    ###
    # Core properties and extensions
    ###

    @property
    def resource_name(self):
        return self._resource_name

    @functools.cached_property
    def _resource_name(self):
        name = f"{super().resource_name}-{self.repo.split('/')[-1]}-{self.branch}".replace(
            "_", "-"
        )

        # TODO: Might have to consider a better hashing strategy based on how
        # a shared cluster is used
        hash = xxhash.xxh32_hexdigest(f"{name}-{self.repo}-{self.branch}")
        max_name_len = 253 - (len(hash) + 1)
        return f"{name[:max_name_len]}-{hash}"

    @property
    def git_bin(self):
        return self._git_bin

    @functools.cached_property
    def _git_bin(self):
        return self.bin("git")

    ###
    # Core methods and properties
    ###

    def kubectl_exec_cmd(self, exe, args):
        cmd = f"git clone {self.repo} --branch {self.branch} --single-branch /project 2> /dev/null || git -C /project pull > /dev/null"
        return f"({cmd}) && {super().kubectl_exec_cmd(exe, args)}"
