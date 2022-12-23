from collections import UserString
import contextlib
import os
import pathlib
import subprocess
from urllib.parse import urlparse

import yaml

import footing.constants


def global_config_dir():
    return pathlib.Path(os.path.expanduser("~")) / ".footing"


def conda_dir():
    return global_config_dir() / "conda"


def local_config_dir(base_dir=None):
    # TODO make this work even when the user is in a folder
    base_dir = base_dir or "."
    return pathlib.Path(base_dir) / ".footing"


def local_config_path(base_dir=None):
    return local_config_dir(base_dir=base_dir) / "config.yml"


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


def shell(cmd, check=True, stdin=None, stdout=None, stderr=None):
    """Runs a subprocess shell with check=True by default"""
    return subprocess.run(cmd, shell=True, check=check, stdin=stdin, stdout=stdout, stderr=stderr)


def conda(cmd, check=True, stdin=None, stdout=None, stderr=None):
    """Runs a conda command based on footing's conda installation"""
    conda_exec = conda_dir() / "bin" / "mamba"
    return shell(f"{conda_exec} {cmd}", check=check, stdin=stdin, stdout=stdout, stderr=stderr)


def conda_install(cmd, *, toolkit, check=True, stdin=None, stdout=None, stderr=None):
    toolkit = footing.toolkit.get(toolkit) if isinstance(toolkit, str) else toolkit
    return conda(
        f"install -n {toolkit.conda_env_name} {cmd}",
        check=check,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
    )


def conda_run(cmd, *, toolkit, check=True, stdin=None, stdout=None, stderr=None):
    toolkit = footing.toolkit.get(toolkit) if isinstance(toolkit, str) else toolkit
    return conda(
        f"run -n {toolkit.conda_env_name} {cmd}",
        check=check,
        stdin=stdin,
        stdout=stdout,
        stderr=stderr,
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

    if auth:
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
