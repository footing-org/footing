import importlib

import footing.cli
import footing.utils


def bin(bin, package=None):
    """Return a binary. Install it if not installed"""
    if not footing.utils.installed_bin(bin):
        footing.cli.pprint(f"install {package or bin}")
        footing.utils.conda_cmd(f"install {package or bin} -y -c conda-forge -n base")

    return footing.utils.bin_path(bin)


def mod(mod, package=None):
    """Return a module. Install it if not installed"""
    if not footing.utils.installed_mod(mod):
        footing.cli.pprint(f"install {package or mod}")
        footing.utils.conda_cmd(f"install {package or mod} -y -c conda-forge -n base")

    return importlib.import_module(mod)