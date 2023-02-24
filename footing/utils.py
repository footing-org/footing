import dataclasses
import os
import pathlib
import platform
import subprocess

import orjson
import xxhash

import footing.ctx
import footing.version


def hash32(val):
    if dataclasses.is_dataclass(val):
        val = orjson.dumps(val)

    return xxhash.xxh32_hexdigest(val)


def hash128(val):
    if dataclasses.is_dataclass(val):
        val = orjson.dumps(val)

    return xxhash.xxh3_128_hexdigest(val)


def install_path():
    footing_file_path = footing.version.metadata.distribution("footing").files[0]
    site_packages_dir = pathlib.Path(
        str(footing_file_path.locate())[: -len(str(footing_file_path))]
    )
    return (site_packages_dir / ".." / ".." / ".." / "..").resolve()


def toolkit_path():
    return install_path() / "toolkit"


def cache_path():
    return install_path() / "cache"


def conda_root_path():
    maj_ver = footing.version.__version__.split(".")[0]
    return install_path() / f"v{maj_ver}"


def condabin_path():
    return conda_root_path() / "condabin"


def bin_path(executable):
    return conda_root_path() / "bin" / executable


def mod_path(mod):
    return conda_root_path() / "lib" / "python3.11" / "site-packages" / mod


def micromamba_path():
    return bin_path("micromamba")


def footing_path():
    return bin_path("footing")


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
        case machine if machine.endswith("64"):
            arch = "64"
        case other:
            arch = "32"

    return f"{system}-{arch}"



def run(cmd, *, check=True, stdin=None, stdout=None, stderr=None, env=None, cwd=None):
    """Runs a subprocess shell with check=True by default"""
    if env or footing.ctx.get().env:
        env = os.environ | footing.ctx.get().env | (env or {})

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
    return f"{micromamba_path()} --no-rc -r {conda_root_path()}"


def conda_cmd(cmd, *, quiet=False):
    """Run a conda command"""
    quiet = " -q" if quiet else ""
    return run(f"{conda_exe()}{quiet} {cmd}")
