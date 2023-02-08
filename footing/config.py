import contextlib
import dataclasses
import importlib
import importlib.util
import sys


_registry = None


@dataclasses.dataclass(kw_only=True)
class Configurable:
    _name: str = None

    @property
    def name(self):
        """The configured name of this object"""
        return getattr(self, "_name", None)


def module(*names):
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
        value._name = name


@ensure_loaded()
def obj(name):
    return _registry.get(name, None)


@ensure_loaded()
def registry():
    return _registry


class Lazy(Configurable):
    pass


def _core():
    import footing.core  # Always do nested imports in the config module

    return footing.core


class compile(Lazy):
    """Compiles chained objects"""

    def __init__(self, *objs):
        self._objs = list(objs)

    def __truediv__(self, obj):
        self._objs.append(obj)
        return self

    def __call__(self, *args, **kwargs):
        assert self._objs

        objs = [task(obj) if isinstance(obj, str) else obj for obj in self._objs]

        obj = objs[-1]
        for val in reversed(objs[:-1]):
            obj._ctx.append(val)

        return obj(*args, **kwargs)


class task(Lazy):
    def __init__(self, *cmd, input=None, output=None):
        self._cmd = cmd
        self._input = input
        self._output = output
        self._ctx = []
        self._deps = []

    def __truediv__(self, obj):
        return compile(self) / obj

    @property
    def obj_class(self):
        return _core().Task

    @property
    def input(self):
        input = self._input or []
        input = [input] if not isinstance(input, (list, tuple)) else input
        input = (_core().Path(val) if isinstance(val, str) else val for val in input)
        return [val() if isinstance(val, Lazy) else val for val in input]

    @property
    def output(self):
        output = self._output or []
        output = [output] if not isinstance(output, (list, tuple)) else output
        output = (_core().Path(val) if isinstance(val, str) else val for val in output)
        return [val() if isinstance(val, Lazy) else val for val in output]

    @property
    def cmd(self):
        return [val() if isinstance(val, Lazy) else val for val in self._cmd]

    @property
    def deps(self):
        deps = self._deps or []
        return [val() if isinstance(val, Lazy) else val for val in deps]

    @property
    def ctx(self):
        ctx = self._ctx or []
        return [val() if isinstance(val, Lazy) else val for val in ctx]

    def __call__(self, *args, **kwargs):
        return self.obj_class(
            cmd=self.cmd,
            input=self.input,
            output=self.output,
            _name=self._name,
            ctx=self.ctx,
            deps=self.deps,
        )
