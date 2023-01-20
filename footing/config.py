import contextlib
import functools
import importlib
import importlib.util
import sys


_registry = None


def plugin(*names):
    return [importlib.import_module(f"footing.{name}") for name in names]


def secret_import(path):
    """Alternative way to import a module that allows importing of hidden
    directories and files."""
    import os
    import imp

    with open(path, "rb") as fp:
        return imp.load_module("config.py", fp, ".footing/config.py", (".py", "rb", imp.PY_SOURCE))


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
        if not name.startswith("_") and hasattr(obj, "ref"):
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
    return _registry[name]


@ensure_loaded()
def registry():
    return _registry