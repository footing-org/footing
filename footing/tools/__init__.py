"""Core configuration for tools"""
import footing.config


def _tools():  # Always do nested imports in the config module
    import footing.tools.core

    return footing.tools.core


class toolkit(footing.config.Runner):
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

    def bin(self, *tasks, input=None, output=None):
        for task in tasks:
            if not isinstance(task, str):
                raise TypeError(f'bin task "{task}" is not a string')
        return bin(self, *tasks, input=input, output=output)


class bin(footing.config.Task):
    def __init__(self, toolkit, *cmd, input=None, output=None):
        self._toolkit = toolkit
        super().__init__(*cmd, input=input, output=output)

    @property
    def obj_class(self):
        return _tools().Bin

    @property
    def obj_kwargs(self):
        return super().obj_kwargs | {"toolkit": self._toolkit}
