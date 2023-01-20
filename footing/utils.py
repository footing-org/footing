import base64
import dataclasses
import importlib
import os
import pathlib
import platform
import subprocess

import shellingham

import footing.version


def b64_encode(val):
    return base64.b64encode(str(val).encode("utf-8")).decode("utf-8")


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


def pprint(msg, *, color=None):
    if color:
        msg = style(msg, color=color)

    print(msg)


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


def conda_exe():
    return f"{micromamba_path()} --no-env --no-rc -r {conda_root_path()}"


def conda_cmd(cmd, *, quiet=False):
    """Run a conda command"""
    quiet = "-q" if quiet else ""
    return run(f"{conda_exe()} {quiet} {cmd}")


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


def detect_platform():
    match platform.system():
        case "Windows":
            system = "win"
        case "Darwin":
            system = "osx"
        case "Linux":
            system = "linux"
        case _:
            raise ValueError(f"Unsupported OS '{system}'")

    machine = platform.machine()
    match machine:
        case "arm64" | "aarch64" | "ppc64le" | "armv6l" | "armv7l":
            arch = machine
        case machine.endswith("64"):
            arch = "64"
        case other:
            arch = "32"

    return f"{system}-{arch}"


def confirm_prompt(question: str, default: str = None, color: str = None) -> bool:
    if color:
        question = style(question, color=color)

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
