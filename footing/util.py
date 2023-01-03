from collections import UserString
import contextlib
import os
import pathlib
import shutil
import subprocess
from urllib.parse import urlparse

import yaml

import footing.constants
import footing.version


def yaml_dump(val, file):
    def yaml_represent_str(self, data):
        return yaml.representer.SafeRepresenter.represent_str(
            self,
            str(data),
        )

    dumper = yaml.SafeDumper
    dumper.add_representer(pathlib.PosixPath, yaml_represent_str)

    with contextlib.ExitStack() as stack:
        if isinstance(file, (pathlib.Path, str)):
            pathlib.Path(file).resolve().parent.mkdir(exist_ok=True, parents=True)
            file = stack.enter_context(open(file, "w"))

        yaml.dump(val, file, Dumper=dumper)


def copy_file(src, dest):
    pathlib.Path(dest).resolve().parent.mkdir(exist_ok=True, parents=True)
    shutil.copy(str(src), str(dest))


def install_dir():
    footing_file_path = footing.version.metadata.distribution("footing").files[0]
    site_packages_dir = pathlib.Path(
        str(footing_file_path.locate())[: -len(str(footing_file_path))]
    )
    return (site_packages_dir / ".." / ".." / ".." / "..").resolve()


def local_cache_dir():
    # Keep the local cache per installation for now in order to support multiple installations
    # one day. We may revisit this later
    return install_dir()


def repo_cache_dir(base_dir=None):
    # TODO make this work even when the user is in a folder
    base_dir = base_dir or "."
    return pathlib.Path(base_dir).resolve() / ".footing"


def conda_dir():
    return install_dir() / "toolkits"


def condabin_dir(check=False):
    condabin_dir = conda_dir() / "condabin"

    if check and not condabin_dir.exists():
        print("condabin dir", condabin_dir, install_dir(), conda_dir())
        raise RuntimeError("Footing is not installed properly. Please use the official installer")

    return condabin_dir


def builds_dir():
    return install_dir() / "builds"


def artifacts_dir():
    return install_dir() / "artifacts"


def footing_exe():
    return conda_dir() / "bin" / "footing"


def git_exe():
    return conda_dir() / "bin" / "git"


def local_config_path(base_dir=None):
    return repo_cache_dir(base_dir=base_dir) / "config.yml"


def local_refs_path(base_dir=None):
    return repo_cache_dir(base_dir=base_dir) / "refs.yml"


def local_config(base_dir=None, create=False):
    """Return the config as a dict"""
    config_path = local_config_path(base_dir=base_dir)
    try:
        with open(config_path) as f:
            return yaml.load(f, Loader=yaml.SafeLoader)
    except FileNotFoundError:
        if create:
            config_path.parent.mkdir(exist_ok=True, parents=True)
            open(config_path, "w").close()
            return {}
        else:
            return None


def shell(cmd, check=True, stdin=None, stdout=None, stderr=None, env=None, cwd=None):
    """Runs a subprocess shell with check=True by default"""
    if env:
        env = {**os.environ, **env}

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


def conda(cmd, check=True, stdin=None, stdout=None, stderr=None, env=None, cwd=None):
    """Runs a conda command based on footing's conda installation"""
    env = env or {}
    env["MAMBA_NO_BANNER"] = "1"

    conda_exec = conda_dir() / "bin" / "mamba"
    return shell(
        f"{conda_exec} {cmd}",
        check=check,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        env=env,
        cwd=cwd,
    )


def conda_install(cmd, *, toolkit, check=True, stdin=None, stdout=None, stderr=None, cwd=None):
    toolkit = footing.toolkit.get(toolkit) if isinstance(toolkit, str) else toolkit
    return conda(
        f"install -n {toolkit.conda_env_name} -y {cmd}",
        check=check,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        cwd=cwd,
    )


def conda_run(cmd, *, toolkit, check=True, stdin=None, stdout=None, stderr=None, cwd=None):
    toolkit = footing.toolkit.get(toolkit) if isinstance(toolkit, str) else toolkit
    return conda(
        f"run -n {toolkit.conda_env_name} --live-stream bash -c '{cmd}'",
        check=check,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        cwd=cwd,
    )


def git(cmd, check=True, stdin=None, stdout=None, stderr=None, cwd=None):
    """Run a git command.

    Tries to directly use the conda-managed git installation first
    """
    git_path = git_exe() if os.path.exists(git_exe()) else "git"

    # TODO: Use "conda run"
    return shell(
        f"{git_path} {cmd}",
        check=check,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
        cwd=cwd,
    )


@contextlib.contextmanager
def cd(path):
    """A context manager for changing into a directory"""
    old_dir = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old_dir)


def format_url(url, auth=False):
    """
    Format a github or gitlab URL into an https path.
    Strip any subdomains and allow for shorthand notation such as gh:Org/Repo
    """
    unformatted_url = url  # For error messages
    url = url.strip().lower()

    if url.startswith("gh://"):
        url = "https://github.com/" + url[5:]
    elif url.startswith("gl://"):
        url = "https://gitlab.com/" + url[5:]

    if "github.com" in url or "gitlab.com" in url:
        if not url.startswith("http"):
            url = "https://" + url
        if url.endswith(".git"):
            url = url[:-4]
    else:
        raise ValueError(f"{unformatted_url} isn't a Github or Gitlab URL.")

    url_parts = urlparse(url)
    if "github.com" in url_parts.netloc:
        url_parts = url_parts._replace(netloc="github.com")
    elif "gitlab.com" in url_parts.netloc:
        url_parts = url_parts._replace(netloc="gitlab.com")

    if auth and footing.constants.GITHUB_API_TOKEN_ENV_VAR in os.environ:
        url_parts = url_parts._replace(
            netloc=f"{os.environ[footing.constants.GITHUB_API_TOKEN_ENV_VAR]}@{url_parts.netloc}"
        )

    url_parts = url_parts._replace(scheme="https")
    return url_parts.geturl()


class RepoURL(UserString):
    def __init__(self, data):
        self._unformatted = data
        self.data = self.format_url(data)

    def format_url(self, data, auth=False):
        return format_url(data)

    def authenticated(self):
        return self.format_url(self.data, auth=True)

    def unformatted(self):
        return self._unformatted

    def parsed(self):
        return urlparse(self.data)


class RepoPath(RepoURL):
    def format_url(self, data, auth=False):
        try:
            return format_url(data, auth=auth)
        except ValueError:  # Assume this is a filesystem path
            return data
