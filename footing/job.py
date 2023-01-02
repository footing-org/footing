import dataclasses

import footing.toolkit
import footing.util


@dataclasses.dataclass
class Job:
    cmd: str = None
    toolkit: str = None

    @classmethod
    def from_def(cls, job):
        return cls(cmd=job["cmd"], toolkit=footing.toolkit.get(job.get("toolkit")))

    @classmethod
    def from_key(cls, key):
        config = footing.util.local_config()

        for job in config["jobs"]:
            if job["key"] == key:
                return cls.from_def(job)

        raise ValueError(f'"{key}" is not a configured job')

    def run(self, *, toolkit=None):
        toolkit = toolkit or self.toolkit or footing.toolkit.get()
        res = footing.util.conda_run(self.cmd, toolkit=toolkit, check=False)
        return res


def get(key):
    return Job.from_key(key)
