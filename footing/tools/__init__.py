"""Core configuration for tools"""
import footing.config


def _tools():
    import footing.tools.core  # Always do nested imports in the config module

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
