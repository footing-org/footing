import contextlib
import dataclasses
import importlib
import importlib.util
import re
import sys


_registry = None


def _core():  # Always do nested imports in the config module
    import footing.core

    return footing.core


@dataclasses.dataclass(kw_only=True)
class Configurable:
    _config_name: str = None

    @property
    def config_name(self):
        """The configured name of this object"""
        return getattr(self, "_config_name", None)


def module(*names):
    if len(names) == 1:
        return importlib.import_module(f"footing.{names[0]}")
    else:
        return [importlib.import_module(f"footing.{name}") for name in names]


def load():
    """Load the footing configuration of a project"""
    global _registry

    if _registry is not None:
        return

    _registry = {}

    # Assume we are in the base directory of a project
    module_name = "loaded_footing_config"
    spec = importlib.util.spec_from_file_location("loaded_footing_config", ".footing/config.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = "loaded_footing_config"
    spec.loader.exec_module(module)

    for name, obj in vars(module).items():
        if not name.startswith("_") and isinstance(obj, Configurable):
            register(**{name: obj})


@contextlib.contextmanager
def ensure_loaded():
    load()
    yield


@ensure_loaded()
def register(**kwargs):
    """Register configured footing objects to names"""
    global _registry

    for name, value in kwargs.items():
        _registry[name] = value
        value._config_name = name


@ensure_loaded()
def obj(name):
    return _registry.get(name, None)


@ensure_loaded()
def registry():
    return _registry


def lazy_eval(obj):
    if isinstance(obj, Lazy):
        return obj()
    elif isinstance(obj, list):
        return [lazy_eval(val) for val in obj]
    elif isinstance(obj, tuple):
        return tuple(lazy_eval(val) for val in obj)
    elif isinstance(obj, dict):
        return {key: lazy_eval(val) for key, val in obj.items()}
    else:
        return obj


class Lazy:
    @property
    def obj_class(self):
        raise NotImplementedError

    @property
    def obj_kwargs(self):
        return {}

    def __call__(self, *args, **kwargs):
        return self.obj_class(**lazy_eval(self.obj_kwargs))


class Task(Lazy, Configurable):
    def __init__(self, *cmd, input=None, output=None):
        self._cmd = list(cmd)
        self._input = input
        self._output = output
        self._ctx = []
        self._deps = []

    @property
    def obj_class(self):
        return _core().Task

    @property
    def obj_kwargs(self):
        return {
            "cmd": self.cmd,
            "input": self.input,
            "output": self.output,
            "_config_name": self._config_name,
            "ctx": self.ctx,
            "deps": self.deps,
        }

    @property
    def input(self):
        input = self._input or []
        input = [input] if not isinstance(input, (list, tuple)) else input
        return [_core().Path(val) if isinstance(val, str) else val for val in input]

    @property
    def output(self):
        output = self._output or []
        output = [output] if not isinstance(output, (list, tuple)) else output
        return [_core().Path(val) if isinstance(val, str) else val for val in output]

    @property
    def ctx(self):
        return self._ctx

    @property
    def deps(self):
        return self._deps

    @property
    def cmd(self):
        return self._cmd


class Shell(Task):
    def __init__(self, *cmd, input=None, output=None, entry=False):
        super().__init__(*cmd, input=input, output=output)
        self._entry = entry

    @property
    def obj_class(self):
        return _core().Shell

    @property
    def obj_kwargs(self):
        return super().obj_kwargs | {"entry": self.entry}

    @property
    def entry(self):
        return self._entry


class sh(Shell):
    pass


class Enterable:
    def __truediv__(self, obj):
        return enter(self) / obj

    def enter(self, obj):
        raise NotImplementedError


class enter(Lazy, Configurable):
    """Enter a list of objects"""

    def __init__(self, *objs):
        self._objs = list(objs)

    def __truediv__(self, obj):
        self._objs.append(obj)
        return self

    def __call__(self, *args, **kwargs):
        assert self._objs

        entered = self._objs[-1]
        for val in reversed(self._objs[:-1]):
            if not isinstance(val, Enterable):
                raise TypeError(f"unsupported operand type for /: '{type(val)}'")

            entered = val.enter(entered)

        return entered(*args, **kwargs)


class Runner(Task, Enterable):
    def enter(self, val):
        if not isinstance(val, Task):
            raise TypeError(f"unsupported operand type for /: '{type(val)}'")

        val._ctx.append(self)
        return val

    def sh(self, *cmd, input=None, output=None, entry=False):
        # TODO: Run a shell when there are no tasks
        return self.enter(Shell(*cmd, input=input, output=output, entry=entry))
