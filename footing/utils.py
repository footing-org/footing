import os
import pathlib
import subprocess

import footing.version


def install_path():
    footing_file_path = footing.version.metadata.distribution("footing").files[0]
    site_packages_dir = pathlib.Path(
        str(footing_file_path.locate())[: -len(str(footing_file_path))]
    )
    return (site_packages_dir / ".." / ".." / ".." / "..").resolve()


def conda_root_path():
    return install_path() / "toolkits"


def condabin_path():
    return conda_root_path() / "condabin"


def footing_path():
    return conda_root_path() / "bin" / "footing"


def style(msg, *, color="green"):
    match color:
        case "green":
            return f"\u001b[32m{msg}\u001b[0m"
        case "red":
            return f"\u001b[31m{msg}\u001b[0m"
        case other:
            raise ValueError(f"Invalid color - {other}")


def shell(cmd, check=True, stdin=None, stdout=None, stderr=None, env=None, cwd=None):
    """Runs a subprocess shell with check=True by default"""
    if env:
        env = os.environ | env

    return subprocess.run(
        cmd,
        shell=True,
        check=check,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        env=env,
        cwd=cwd,
    )
