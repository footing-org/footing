import dataclasses
import os
import subprocess

import footing.obj
import footing.utils


def installed():
    return footing.utils.installed("kubectl", "git")


def install():
    footing.cli.pprint("install k8s plugin")
    return footing.utils.conda_cmd("install kubernetes git -y -c conda-forge -n base", quiet=True)


def repo():
    """Retrieve the URL of the current repo"""
    if "FOOTING_POD_REPO" in os.environ:
        return os.environ["FOOTING_POD_REPO"]

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
    if "FOOTING_POD_BRANCH" in os.environ:
        return os.environ["FOOTING_POD_BRANCH"]

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

    @property
    def entry(self):
        return {
            "build": footing.obj.Entry(method=self.build),
        }

    def lazy_post_init(self):
        """Lazily compute post_init properties"""
        self.repo = self.repo or repo()
        self.branch = self.branch or branch()

    def bootstrap(self):
        if not installed():
            install()

        self.render()

    def run(self, func):
        """Run a function"""
        self.bootstrap()

    def build(self):
        # TODO: Run these methods automatically as part of build process. Do the same
        # for caching
        self.bootstrap()
