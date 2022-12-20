"""
Utilities for accessing and traversing different git forges, along with pulling down
remote templates.

Currently Github and Gitlab are supported
"""
import abc
import collections
import os

import gitlab
import gitlab.const
import requests
import tldextract

import footing.check


def from_url(url):
    """
    Given a forge url, such as Github or Gitlab, return a client for accessing
    the repository information.

    Args:
        url (str): A forge or repo URL.
            For example, a Github organization or user (e.g. github.com/Organization)
            or a Gitlab group (e.g. gitlab.com/my/group). Shorthand such as gh:Organization
            can be used
    """
    url = footing.utils.format_url(url)
    if url.startswith("https://github.com"):
        return Github()
    elif url.startswith("https://gitlab.com"):
        return Gitlab()
    else:
        # This case is caught by format_url()
        raise AssertionError()


class Forge(metaclass=abc.ABCMeta):
    """The base class for all git forges.

    Forges must implement both ``ls`` for listing templates/projects
    and ``get_latest_template_version`` for finding the latest version
    of a template. The ``api_token_env_var_name`` property must also
    be configured.
    """

    @abc.abstractmethod
    def ls(self, url):
        """Implements ls for the forge"""
        pass

    @property
    @abc.abstractmethod
    def api_token_env_var_name(self):
        """Returns the environment variable name for configuring an API token"""
        pass

    @abc.abstractmethod
    def get_latest_template_version(self, template):
        """Finds the latest version of a template using an API

        By default, the latest version of a template is used with standard
        git calls and SSH auth. However, one must implement this method
        as a fallback in case only API access is available.
        """
        pass


class Github(Forge):
    """A Github forge"""

    @property
    def api_token_env_var_name(self):
        return footing.constants.GITHUB_API_TOKEN_ENV_VAR

    def _call_api(self, verb, url, **request_kwargs):
        """Perform a github API call

        Args:
            verb (str): Can be "post", "put", or "get"
            url (str): The base URL with a leading slash for Github API (v3)
            auth (str or HTTPBasicAuth): A Github API token or a HTTPBasicAuth object
        """
        footing.check.has_env_vars(footing.constants.GITHUB_API_TOKEN_ENV_VAR)
        api_token = os.environ[footing.constants.GITHUB_API_TOKEN_ENV_VAR]
        api = f"https://api.github.com{url}"
        auth_headers = {"Authorization": f"token {api_token}"}
        headers = {**auth_headers, **request_kwargs.pop("headers", {})}
        return getattr(requests, verb)(api, headers=headers, **request_kwargs)

    def _get(self, url, **request_kwargs):
        """Github API get"""
        return self._call_api("get", url, **request_kwargs)

    def _parse_link_header(self, headers):
        """A utility function that parses Github's link header for pagination."""
        links = {}
        if "link" in headers:
            link_headers = headers["link"].split(", ")
            for link_header in link_headers:
                (url, rel) = link_header.split("; ")
                url = url[1:-1]
                rel = rel[5:-1]
                links[rel] = url
        return links

    def _code_search(self, query, forge=None):
        """Performs a Github API code search

        Args:
            query (str): The query sent to Github's code search
            root (str, optional): The root being searched in Github

        Returns:
            dict: A dictionary of repository information keyed on the git SSH url

        Raises:
            `InvalidForgeError`: When ``forge`` is invalid
        """
        headers = {"Accept": "application/vnd.github.v3.text-match+json"}

        resp = self._get(
            "/search/code",
            params={"q": query, "per_page": 100},
            headers=headers,
        )

        if resp.status_code == requests.codes.unprocessable_entity and forge:
            raise footing.exceptions.InvalidForgeError(f'Invalid Github organization - "{forge}"')
        resp.raise_for_status()

        resp_data = resp.json()

        repositories = collections.defaultdict(dict)
        while True:
            repositories.update(
                {
                    f'gh:{repo["repository"]["full_name"]}': repo["repository"]
                    for repo in resp_data["items"]
                }
            )

            next_url = self._parse_link_header(resp.headers).get("next")
            if next_url:
                resp = requests.get(next_url, headers=headers)
                resp.raise_for_status()
                resp_data = resp.json()
            else:
                break

        return repositories

    def get_latest_template_version(self, template):
        """Tries to obtain the latest template version with the Github API"""
        repo_path = footing.utils.parse_url(template).path.strip("/")
        api = f"/repos/{repo_path}/commits"

        last_commit_resp = self._get(api, params={"per_page": 1})
        last_commit_resp.raise_for_status()

        content = last_commit_resp.json()
        assert len(content) == 1, "Unexpected Github API response"
        return content[0]["sha"]

    def ls(self, url):
        """Return a list of repositories under the forge path or the template (if provided)."""
        url = footing.util.RepoURL(url)
        url_parts = url.parsed()
        path_parts = url_parts.path.strip("/").split("/")

        if not path_parts:
            raise ValueError(f"{url} has no Github org")
        elif len(path_parts) == 1:
            search_q = f"user:{path_parts[0]} filename:{footing.constants.FOOTING_CONFIG_FILE}"
        elif len(path_parts) == 2:
            search_q = (
                f"user:{path_parts[0]} filename:{footing.constants.FOOTING_CONFIG_FILE}"
                f" {url_parts.path.strip('/')}"
            )
        else:
            raise ValueError(f"{url.unformatted()} is an invalid Github repository URL")

        results = self._code_search(search_q, forge=url)
        return collections.OrderedDict(
            sorted(
                [
                    (key, value["description"] or "(no description found)")
                    for key, value in results.items()
                ]
            )
        )


class Gitlab(Forge):
    """A Gitlab forge"""

    @property
    def api_token_env_var_name(self):
        return footing.constants.GITLAB_API_TOKEN_ENV_VAR

    def get_client(self, template):
        footing.check.has_env_vars(self.api_token_env_var_name)
        url_parts = footing.utils.parse_url(template)
        gitlab_url = f"{url_parts.scheme}://{url_parts.netloc}"
        api_token = os.environ[self.api_token_env_var_name]
        return gitlab.Gitlab(url=gitlab_url, private_token=api_token)

    def get_latest_template_version(self, template):  # pragma: no cover
        """Tries to obtain the latest template version with the Gitlab API"""
        gl = self.get_client(template)
        project = gl.projects.get(footing.utils.parse_url(template).path)
        sha = project.commits.list()[0].id

        return sha

    def _get_gitlab_group(self, forge):
        """Given a forge, return a gitlab url and group"""
        gitlab_url = footing.util.RepoURL(forge)
        url_parts = gitlab_url.parsed()
        group = url_parts.path.strip("/")

        # If users are listing templates on gitlab.com and not a self-hosted gitlab,
        # do not allow them to query the root gitlab.com
        is_self_hosted = tldextract.extract(forge).domain != "gitlab"

        if not group and not is_self_hosted:
            raise footing.exceptions.InvalidGitlabGroupError(
                "Must provide a gitlab group, for example gitlab.com/group"
            )

        return gitlab_url, group

    def ls(self, forge):  # pragma: no cover
        """Return a list of repositories under the forge path or the template (if provided)."""
        # TODO: Implement this again. We will likely split the ls command into "templates"
        # and "projects"
        raise RuntimeError("Gitlab currently not supported for this operation")

        # gitlab_url, group = self._get_gitlab_group(forge)

        # gl = self.get_client(forge)
        # if group:
        #     # Search under a group if one is specified
        #     gl = gl.groups.get(group)

        # # Search for either templates (with cookiecutter.json) or projects that have been made
        # # from the template. Note - advanced search must be turned on for the Gitlab instance
        # if not template:
        #     results = gl.search(
        #         gitlab.const.SEARCH_SCOPE_BLOBS,
        #         search="filename:cookiecutter.json",
        #     )
        # else:
        #     results = gl.search(
        #         gitlab.const.SEARCH_SCOPE_BLOBS,
        #         search="{} filename:footing.yaml".format(template),
        #     )

        # # Fetch projects associated with search results
        # gl = self.get_client(forge)
        # projects = [gl.projects.get(r["project_id"]) for r in results]

        # return collections.OrderedDict(
        #     sorted(
        #         [
        #             (
        #                 p.ssh_url_to_repo,
        #                 p.description or "(no description found)",
        #             )
        #             for p in projects
        #         ]
        #     )
        # )
