from collections import UserString
import contextlib
import os
import subprocess
from urllib.parse import urlparse

import footing.constants


def shell(cmd, check=True, stdin=None, stdout=None, stderr=None):
    """Runs a subprocess shell with check=True by default"""
    return subprocess.run(cmd, shell=True, check=check, stdin=stdin, stdout=stdout, stderr=stderr)


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
