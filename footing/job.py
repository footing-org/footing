import dataclasses

import footing.toolkit
import footing.util


@dataclasses.dataclass
class Job:
    name: str
    cmd: str
    toolkit: str = None
    _def: dict = None

    @property
    def uri(self):
        return f"job:{self.name}"

    @classmethod
    def from_def(cls, job):
        return cls(
            name=job["name"],
            cmd=job["cmd"],
            toolkit=footing.toolkit.get(job.get("toolkit")),
            _def=job,
        )

    @classmethod
    def from_name(cls, name):
        config = footing.util.local_config()

        for job in config["jobs"]:
            if job["name"] == name:
                return cls.from_def(job)

        raise ValueError(f'"{name}" is not a configured job')

    def run(self, *, toolkit=None):
        toolkit = toolkit or self.toolkit or footing.toolkit.get()
        res = footing.util.conda_run(self.cmd, toolkit=toolkit, check=False)
        return res


def get(name):
    return Job.from_name(name)
