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
        self._env = env
        self.ports = ports
        self.image_pull_policy = image_pull_policy
        self.command = command
        self.args = args

    @property
    def env(self):
        return [_k8s().Env(name=name, value=value) for name, value in self._env.items()]

    @property
    def obj_class(self):
        return _k8s().Service

    @property
    def obj_kwargs(self):
        keys = (key.removeprefix("_") for key in self.__dict__.keys())
        return {key: getattr(self, key) for key in keys}


class sleepy(service):
    @property
    def obj_class(self):
        return _k8s().Sleepy


class pod(footing.config.Task, footing.config.Contextual):
    def __init__(self, *services, name=None):
        self._services = list(services)
        self._name = name

    def enter(self, obj):
        return run(pod=self, task=obj)

    @property
    def obj_class(self):
        return _k8s().Pod

    @property
    def obj_kwargs(self):
        return {"services": self.services, "name": self.name}

    @property
    def services(self):
        return [service(val) if isinstance(val, str) else val for val in self._services]

    @property
    def name(self):
        return self._name


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


class git_runner(pod):
    @property
    def obj_class(self):
        return _k8s().GitRunner
