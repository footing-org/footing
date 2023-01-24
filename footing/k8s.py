import dataclasses

import footing.obj
import footing.utils


def installed():
    return footing.utils.installed("kubectl", "git")


def install():
    footing.cli.pprint("install k8s plugin")
    return footing.utils.conda_cmd("install kubernetes git -y -c conda-forge -n base", quiet=True)


@dataclasses.dataclass
class Cluster(footing.obj.Obj):
    def build(self):
        pass


@dataclasses.dataclass
class Pod(footing.obj.Obj):
    @property
    def entry(self):
        return {
            "build": footing.obj.Entry(method=self.build),
        }

    def build(self):
        print("build")
        if not installed():
            install()
