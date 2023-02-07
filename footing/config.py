import contextlib
import functools
import importlib
import importlib.util
import sys


_registry = None


class Configurable:
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
def obj(name, init=False):
    obj = _registry.get(name, None)

    if obj and init:
        obj.init()

    return obj


@ensure_loaded()
def registry():
    return _registry
