import dataclasses
import functools
import os
import pathlib
import subprocess
import tempfile
import textwrap

import xxhash

import footing.obj
import footing.utils


def installed():
    return footing.utils.installed("kubectl", "git")


def install():
    footing.cli.pprint("install k8s plugin")
    return footing.utils.conda_cmd("install kubernetes git -y -c conda-forge -n base", quiet=True)


def repo():
    """Retrieve the URL of the current repo"""
    out = footing.utils.run("git config --get remote.origin.url", stdout=subprocess.PIPE)
    url = out.stdout.decode("utf-8")

    if url.startswith("git@github.com"):
        repo = url.strip().split(":", 1)[1][:-4]
        return f"https://github.com/{repo}"
    elif url.startswith("https://github.com"):
        return url
    else:
        raise ValueError(f'Invalid git remote repo URL - "{url}"')


def branch():
    """Retrieve the branch of the current repo"""
    out = footing.utils.run("git rev-parse --abbrev-ref HEAD", stdout=subprocess.PIPE)
    return out.stdout.decode("utf-8").strip()


@dataclasses.dataclass
class Cluster(footing.obj.Obj):
    def build(self):
        pass


@dataclasses.dataclass
class Pod(footing.obj.Obj):
    repo: str = None
    branch: str = None
    spec: str = None

    @property
    def entry(self):
        return {
            "build": footing.obj.Entry(method=self.build),
            "delete": footing.obj.Entry(method=self.delete),
            "/": footing.obj.Entry(method=self.exec),
        }

    @property
    def resource_name(self):
        return self._resource_name

    @functools.cached_property
    def _resource_name(self):
        name = self.name or "pod"
        repo = self.repo.split("/")[-1]
        name += f"-{repo}-{self.branch}"
        name = name.replace("_", "-")

        # TODO: Might have to consider a better hashing strategy based on how
        # a shared cluster is used
        hash = xxhash.xxh32_hexdigest(f"{name}-{self.repo}-{self.branch}")
        max_name_len = 253 - (len(hash) + 1)
        return f"{name[:max_name_len]}-{hash}"

    def lazy_post_init(self):
        """Lazily compute post_init properties"""
        self.repo = self.repo or repo()
        self.branch = self.branch or branch()
        self.spec = textwrap.dedent(
            f"""
            apiVersion: v1
            kind: Pod
            metadata:
              name: {self.resource_name}
            spec:
              containers:
              - name: runner
                image: wesleykendall/footing:latest
                imagePullPolicy: Always 
                command: ["/bin/bash", "-c", "--"]
                args: ["trap : TERM INT; sleep infinity & wait"]
                env:
                - name: PYTHONUNBUFFERED
                  value: "1"
            """
        )

    def bootstrap(self):
        if not installed():
            install()

        self.render()

    def exec(self, exe, args, retry=True):
        """Exec a function in this pod"""
        self.build()

        try:
            if not exe:
                for name in footing.config.registry():
                    footing.cli.pprint(name, weight=None, icon=False)
            else:
                kubectl = footing.utils.bin_path("kubectl")
                git = footing.utils.bin_path("git")

                # git is in the PATH of the container, so no need to provide an absolute path
                footing.cli.pprint("provisioning")
                cmd = f"git clone {self.repo} --branch {self.branch} --single-branch /project 2> /dev/null || git -C /project pull > /dev/null"
                cmd = f"({cmd}) && footing {exe}"

                footing.utils.run(
                    f"{kubectl} exec {self.resource_name} -- bash -c '{cmd}'",
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
        self.bootstrap()
        kubectl = footing.utils.bin_path("kubectl")

        if self.is_cached and cache:
            return

        footing.cli.pprint("creating pod")

        with tempfile.TemporaryDirectory() as tmp_d:
            pod_yml_path = pathlib.Path(tmp_d) / "pod.yml"
            with open(pod_yml_path, "w") as f:
                f.write(self.spec)

            footing.utils.run(f"{kubectl} apply -f {pod_yml_path}")

        footing.utils.run(
            f"{kubectl} wait --for=condition=ready --timeout '-1s' pod {self.resource_name}"
        )

        self.write_cache()

    def delete(self):
        self.bootstrap()
        kubectl = footing.utils.bin_path("kubectl")

        self.delete_cache()

        try:
            footing.utils.run(f"{kubectl} delete pod {self.resource_name}", stderr=subprocess.PIPE)
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8").strip() if exc.stderr else ""
            if stderr == f'Error from server (NotFound): pods "{self.resource_name}" not found':
                pass
            else:
                raise
