"""Core configuration for tools"""
import copy

import footing.config


def _core():  # Always do nested imports in the config module
    import footing.core

    return footing.core


def _tools():  # Always do nested imports in the config module
    import footing.tools.core

    return footing.tools.core


class toolkit(footing.config.task):
    @property
    def obj_class(self):
        return _tools().Toolkit

    @property
    def cmd(self):
        # Group strings into an installed packages
        cmd = []
        packages = None
        for val in super().cmd:
            if isinstance(val, str):
                if not packages:
                    packages = [val]
                    cmd.append(packages)
                else:
                    packages.append(val)
            else:
                cmd.append(val)

        # Now that we have groups, translate the command into
        # installer objects
        return [
            _tools().Install(packages=val) if isinstance(val, (list, tuple)) else val
            for val in cmd
        ]

    @property
    def bin(self):
        return bin(self)


class bin(footing.config.task):
    def __init__(self, toolkit):
        self._toolkit = toolkit
        super().__init__()

    @property
    def obj_class(self):
        return _tools().Bin

    @property
    def obj_kwargs(self):
        return super().obj_kwargs | {"toolkit": self._toolkit}

    def enter(self, obj):
        bin = copy.copy(self)
        bin._cmd = bin._cmd + [obj]
        return bin
