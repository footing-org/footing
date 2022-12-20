"""
footing.init
~~~~~~~~~~~~~

Initializes a project from a template
"""
import contextlib
import os
import subprocess
import unittest.mock

from cookiecutter.exceptions import NonTemplatedInputDirException
from cookiecutter.find import logger as find_logger
import cookiecutter.generate as cc_generate
import cookiecutter.hooks as cc_hooks

import footing.check
import footing.constants
import footing.utils


def _patched_find_template(repo_dir):
    """Used to patch cookiecutter's ``find_template`` function."""
    find_logger.debug("Searching %s for the project template.", repo_dir)

    repo_dir_contents = os.listdir(repo_dir)

    project_template = None
    for item in repo_dir_contents:
        if ("cookiecutter" in item or "footing" in item) and "{{" in item and "}}" in item:
            project_template = item
            break

    if project_template:
        project_template = os.path.join(repo_dir, project_template)
        find_logger.debug("The project template appears to be %s", project_template)
        return project_template
    else:
        raise NonTemplatedInputDirException


def _patched_run_hook(hook_name, project_dir, context):
    """Used to patch cookiecutter's ``run_hook`` function.

    This patched version ensures that the footing.yaml file is created before
    any cookiecutter hooks are executed
    """
    if hook_name == "post_gen_project":
        with footing.utils.cd(project_dir):
            footing.utils.write_footing_config(
                context["cookiecutter"],
                context["template"],
                context["version"],
            )
    return cc_hooks.run_hook(hook_name, project_dir, context)


def _generate_files(repo_dir, config, template, version):
    """Uses cookiecutter to generate files for the project.

    Monkeypatches cookiecutter's "run_hook" to ensure that the footing.yaml file is
    generated before any hooks run. This is important to ensure that hooks can also
    perform any actions involving footing.yaml
    """
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            unittest.mock.patch(
                "cookiecutter.generate.find_template", side_effect=_patched_find_template
            )
        )
        stack.enter_context(
            unittest.mock.patch("cookiecutter.generate.run_hook", side_effect=_patched_run_hook)
        )

        cc_generate.generate_files(
            repo_dir=repo_dir,
            context={
                "cookiecutter": config,
                "footing": config,
                "template": template,
                "version": version,
            },
            overwrite_if_exists=False,
            output_dir=".",
        )


@footing.utils.set_cmd_env_var("init")
def init(template, version=None, parameters=None, cwd=None):
    """Initialize a new project from a template

    Note that the `footing.constants.FOOTING_ENV_VAR` is set to 'init' during the duration
    of this function.

    Args:
        template (str): The git path to a template
        version (str, optional): The version of the template to use when updating. Defaults
            to the latest version
        parameters (dict, optional): Parameters to use for setup. Will not prompt
        cwd (str, optional): The directory under which to create the project
    """
    # footing.check.not_in_git_repo()
    cwd = cwd or os.getcwd()
    cc_repo_dir, config = footing.utils.get_cookiecutter_config(
        template, version=version, parameters=parameters
    )

    if not version:
        with footing.utils.cd(cc_repo_dir):
            try:
                ret = footing.utils.shell(
                    "git rev-parse HEAD", stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
                version = ret.stdout.decode("utf-8").strip()
            except subprocess.CalledProcessError:
                version = None  # For local templates with no git repo.

    with footing.utils.cd(cwd):
        _generate_files(repo_dir=cc_repo_dir, config=config, template=template, version=version)
