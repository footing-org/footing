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


class Token:
    """Tokenized part of a compilation string"""

    def __init__(self, val):
        self._val = val

    def __str__(self):
        return self._val

    def __call__(self):
        # Interpret the token as a footing object
        parts = self._val.split(".")
        loaded = obj(parts[0])

        if not loaded:
            raise ValueError(f'Could not load object "{parts[0]}"')

        for part in parts[1:]:
            loaded = getattr(loaded, part)

        return loaded


def compile(expr):
    """Compile a command string into a task"""
    enter_parts = expr.split("/")
    compiled_parts = []

    for i, enter_part in enumerate(enter_parts):
        compiled_part = enter_part

        if i == 0 or not re.match(r"^\w", enter_parts[i - 1]):
            sub_parts = enter_part.split(".")

            compiled_part = obj(sub_parts[0])
            if not compiled_part:
                raise ValueError(f'Task does not exist - "{sub_parts[0]}"')

            for sub_part in sub_parts[1:]:
                compiled_part = getattr(compiled_part, sub_part)
        elif i != len(enter_parts) - 1:
            # If this case happens, a string came after another string
            raise ValueError("Invalid task defintion")

        compiled_parts.append(compiled_part)

    compiled = compiled_parts[0]
    for compiled_part in compiled_parts[1:]:
        compiled /= compiled_part

    return compiled


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


class Lazy(Configurable):
    @property
    def obj_class(self):
        raise NotImplementedError

    @property
    def obj_kwargs(self):
        return {}

    def __call__(self, *args, **kwargs):
        return self.obj_class(**lazy_eval(self.obj_kwargs))


class Enterable:
    def __truediv__(self, obj):
        return enter(self) / obj

    def enter(self, obj):
        raise NotImplementedError


class enter(Lazy):
    """Enter a list of objects"""

    def __init__(self, *objs):
        self._objs = list(objs)

    def __truediv__(self, obj):
        self._objs.append(obj)
        return self

    def __call__(self, *args, **kwargs):
        assert self._objs

        # Always start with a new task that can be modified during Lazy.enter()
        compiled = task(self._objs[-1])

        for val in reversed(self._objs[:-1]):
            val = task(val) if isinstance(val, str) else val
            compiled = val.enter(compiled)

        return compiled(*args, **kwargs)


class task(Lazy, Enterable):
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

    def enter(self, obj):
        obj._ctx.append(self)
        return obj

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
    def cmd(self):
        return self._cmd

    @property
    def deps(self):
        return self._deps

    @property
    def ctx(self):
        return self._ctx
