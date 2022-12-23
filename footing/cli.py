"""
The footing CLI contains commands for setting up, listing, and updating projects.

Commands
~~~~~~~~

* ``footing bootstrap`` - Bootstrap footing's dependencies
* ``footing init`` - Sets up a new project
* ``footing ls`` - Lists all templates and projects created with those templates
* ``footing sync`` - Updates the project to the latest template version
* ``footing clean`` - Cleans up any temporary resources used by footing
* ``footing switch`` - Switch a project to a different template
"""
import os
import sys

import click
import pkg_resources

import footing
import footing.bootstrap
import footing.cast
import footing.clean
import footing.exceptions
import footing.ls
import footing.shell
import footing.sync
import footing.toolkit
import footing.workspace


def _parse_parameters(parameters):
    parsed_parameters = None
    if parameters:
        for parameter in parameters:
            assert "=" in parameter

        parsed_parameters = {
            parameter.split("=", 1)[0]: parameter.split("=", 1)[1] for parameter in parameters
        }

    return parsed_parameters


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--version", is_flag=True, help="Show version")
@click.option("--banner", is_flag=True, help="Print banner")
def main(ctx, version, banner):
    if version:
        print("footing {}".format(pkg_resources.get_distribution("footing").version))
    elif banner:
        click.echo(footing.constants.BANNER["dollar"])
    elif not ctx.invoked_subcommand:
        print(ctx.get_help())


@main.command()
def bootstrap():
    """
    Bootstraps footing's other dependencies
    """
    footing.bootstrap.bootstrap()


###
# Toolkits
###


def _toolkit_sync(key=None):
    if key:
        footing.toolkit.get(key).sync()
    else:
        workspace = footing.workspace.get()
        if workspace.toolkit:
            workspace.toolkit.sync()


@main.group()
def toolkit():
    """
    Manage toolkits.
    """
    pass


@toolkit.command("sync")
@click.argument("key", nargs=1, required=False)
def toolkit_sync(key):
    """
    Sync a toolkit.
    """
    _toolkit_sync(key)


@toolkit.command("ls")
@click.option("--active", is_flag=True)
def toolkit_ls(active):
    """
    List toolkits
    """
    toolkits = footing.toolkit.ls(active=active)
    for toolkit in toolkits:
        click.echo(toolkit.key)


###
# Casts
###


@main.group()
def cast():
    """
    Manage casts.
    """
    pass


@cast.command("init")
@click.argument("mold", nargs=1, required=True)
@click.option(
    "-v",
    "--version",
    default=None,
    help="Git SHA or branch of mold to use for creation",
)
@click.option(
    "-p",
    "--parameter",
    "parameters",
    multiple=True,
    default=None,
    help="Mold parameters to inject. Will avoid prompting.",
)
@click.option("-d", "--dir", "cwd", default=None, help="Setup the project in this directory.")
def cast_init(mold, version, parameters, cwd):
    """
    Initializes a cast. Takes a git path to the mold as returned
    by "footing ls". In order to start a project from a
    particular version (instead of the latest), use the "-v" option.
    """
    parameters = _parse_parameters(parameters)
    cast = footing.cast.Cast.from_url(footing.util.RepoPath(mold), version=version)
    cast.init(version=version, parameters=parameters, cwd=cwd)


# @cast.command()
# @click.option("-c", "--check", is_flag=True, help="Check to see if up to date")
# @click.option(
#     "-e",
#     "--enter-parameters",
#     is_flag=True,
#     help="Enter template parameters on update",
# )
# @click.option(
#     "-v",
#     "--version",
#     default=None,
#     help="Git SHA or branch of template to use for update",
# )
# @click.option(
#     "-p",
#     "--parameter",
#     "parameters",
#     multiple=True,
#     default=None,
#     help="Template parmaeters to inject. Will avoid prompting.",
# )
# def update(check, enter_parameters, version, parameters):
#     """
#     Synchronize project with latest template. Must be inside of the project
#     folder to run.

#     Using "-e" will prompt for re-entering the template parameters again
#     even if the project is up to date.

#     Use "-v" to update to a particular version of a template.

#     Using "-c" will perform a check that the project is up to date
#     with the latest version of the template (or the version specified by "-v").
#     No updating will happen when using this option.
#     """
#     parameters = _parse_parameters(parameters)

#     if check:
#         if footing.sync.up_to_date(version=version):
#             print("Footing project is up to date")
#         else:
#             msg = (
#                 "This footing project is out of date with the latest template."
#                 ' Synchronize your project by running "footing sync" and commiting changes.'
#             )
#             raise footing.exceptions.NotUpToDateWithTemplateError(msg)
#     else:
#         footing.sync.sync(
#             new_version=version, enter_parameters=enter_parameters, parameters=parameters
#         )


# @main.command()
# @click.argument("url", nargs=1, required=True)
# @click.option(
#     "-l",
#     "--long-format",
#     is_flag=True,
#     help="Print extended information about results",
# )
# def ls(url, long_format):
#     """
#     List footing projects. Enter a git forge URL, such as a Github
#     user or Gitlab group, to list all templates under the forge.
#     Provide the template URL to list all projects
#     associated with the template.

#     Use "-l" to print the repository descriptions of templates
#     or projects.
#     """
#     results = footing.ls.ls(url)
#     for url, description in results.items():
#         if long_format:
#             print(url, "-", description)
#         else:
#             print(url)


# @main.command()
# def clean():
#     """
#     Cleans temporary resources created by footing, such as the footing sync branch
#     """
#     footing.clean.clean()


# @main.command()
# @click.argument("template", nargs=1, required=True)
# @click.option(
#     "-v",
#     "--version",
#     default=None,
#     help="Git SHA or branch of template to use for update",
# )
# def switch(template, version):
#     """
#     Switch a project's template to a different template.
#     """
#     footing.sync.sync(new_template=template, new_version=version)


###
# Workspaces
###


@main.command()
@click.option(
    "-t",
    "--toolkit",
    default=None,
)
def set(toolkit):
    """
    Sets workspace values
    """
    footing.workspace.set(toolkit=toolkit)


@main.command()
@click.option(
    "-t",
    "--toolkit",
    is_flag=True,
)
def unset(toolkit):
    """
    Unsets workspace values
    """
    footing.workspace.unset(toolkit=toolkit)


@main.command()
def activate():
    """
    Shell instructions for activating a workspace
    """
    if not os.environ.get("_FOOTING_ACTIVATE"):
        click.echo('Run "footing shell" in order to activate workspaces', err=True)
        sys.exit(1)

    config = footing.util.local_config()
    if not config:
        sys.exit(1)

    workspace = footing.workspace.get()
    if not workspace.toolkit:
        click.echo("Set a default toolkit to activate it", err=True)
        sys.exit(1)
    else:
        click.echo(workspace.toolkit.conda_env_name)


@main.command()
def shell():
    shell = footing.shell.Shell.get()
    shell.init()


@main.command()
@click.option(
    "-t",
    "--toolkit",
    "toolkits",
    multiple=True,
    default=None,
    help="Toolkits to sync.",
)
def sync(toolkits):
    """Synchronize a workspace"""
    if toolkits:
        for key in toolkits:
            _toolkit_sync(key)
    else:
        _toolkit_sync()
