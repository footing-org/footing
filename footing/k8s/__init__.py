import copy

import footing.config


def _k8s():  # Always do nested imports in the config module
    import footing.k8s.core

    return footing.k8s.core


class service(footing.config.Lazy):
    def __init__(
        self,
        image,
        name=None,
        env=None,
        ports=None,
        image_pull_policy=None,
        command=None,
        args=None,
    ):
        self.image = image
        self.name = name
        self.env = env
        self.ports = ports
        self.image_pull_policy = image_pull_policy
        self.command = command
        self.args = args

    @property
    def obj_class(self):
        return _k8s().Service

    @property
    def obj_kwargs(self):
        return self.__dict__


class sleepy(service):
    @property
    def obj_class(self):
        return _k8s().Sleepy


class pod(footing.config.Runner):
    def __init__(self, *services):
        self._services = list(services)

    def enter(self, obj):
        return run(pod=self, task=obj)

    @property
    def obj_class(self):
        return _k8s().Pod

    @property
    def obj_kwargs(self):
        return {"services": self.services}

    @property
    def services(self):
        return [service(val) if isinstance(val, str) else val for val in self._services]


class run(footing.config.Task):
    def __init__(self, pod, task):
        self._pod = pod
        self._task = task

    @property
    def obj_kwargs(self):
        return {"pod": self._pod, "task": self._task}

    @property
    def obj_class(self):
        return _k8s().Run


class runner(pod):
    @property
    def obj_class(self):
        return _k8s().Runner
