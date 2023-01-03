"""
footing.ls
~~~~~~~~~~

Lists all footing templates and projects spun up with those templates
"""
import footing.forge


@footing.utils.set_cmd_env_var("ls")
def ls(url):
    """Lists all templates or projects associated with a URL.

    The ``url`` must be either a Github organization/user (e.g. github.com/organization),
    Gitlab group (e.g. gitlab.com/my/group), or template URL.

    Note that the `footing.constants.FOOTING_ENV_VAR` is set to 'ls' for the duration of this
    function.

    Args:
        url (str): A Github organization (github.com/Organization),
            gitlab group (gitlab.com/my/group), or template URL.

    Returns:
        dict: A dictionary of repository information nameed on the url.

    Raises:
        `ValueError`: When ``url`` is invalid
    """
    client = footing.forge.from_url(url)
    return client.ls(url)
