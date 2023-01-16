import importlib
import os
import pathlib
import subprocess

import shellingham

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


def micromamba_path():
    return conda_root_path() / "bin" / "micromamba"


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


def run(cmd, *, check=True, stdin=None, stdout=None, stderr=None, env=None, cwd=None):
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


def conda_cmd(cmd):
    """Run a conda command"""
    micromamba = f"{micromamba_path()} -q --no-env --no-rc -r {conda_root_path()}"
    return run(f"{micromamba} {cmd}")


def conda_run(cmd, *, name):
    """Run a command within a conda env"""
    return conda_cmd(f"run -n {name} {cmd}")


def detect_shell():
    try:
        return shellingham.detect_shell()[0]
    except (RuntimeError, shellingham.ShellDetectionFailure):
        if os.name in ("posix", "nt"):
            if os.name == "posix":
                shell = os.environ.get("SHELL")
            elif os.name == "nt":
                shell = os.environ.get("COMSPEC")

            return pathlib.Path(shell).stem


def confirm_prompt(question: str, default: str = None) -> bool:
    if default is None:
        choices = "[y/n]"
    elif default == "y":
        choices = "[Y/n]"
    elif default == "n":
        choices = "[y/N]"
    else:
        raise ValueError("Invalid default value")

    reply = None
    while reply not in ("y", "n"):
        reply = input(f"{question} {choices}: ").casefold() or default

    return reply == "y"
