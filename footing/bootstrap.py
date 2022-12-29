"""
footing.bootstrap
~~~~~~~~~~~~~~~~~

Bootstraps footing's internal dependencies
"""
import pathlib
import subprocess

import click

import footing.util
import footing.version


def bootstrap(system=False):
    """Bootstraps footing's internal dependencies and finalizes installation"""
    condabin_dir = footing.util.condabin_dir(check=True)

    # Footing needs git and terraform to run
    footing.util.conda("install -q -n base git==2.39.0 terraform==1.3.5 -y")

    # Create soft links to global tools in the conda bin dir
    with footing.util.cd(condabin_dir):
        footing.util.shell(
            "ln -sf ../bin/footing footing",
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        footing.util.shell(
            "ln -sf ../bin/git git", check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        footing.util.shell(
            "ln -sf ../bin/terraform terraform",
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    if system:
        click.echo(
            click.style(
                "Enter your password if prompted to install footing in /usr/local/bin/.",
                fg="green",
            )
        )
        footing.util.shell(
            f"sudo ln -sf {footing.util.footing_exe()} /usr/local/bin/footing", check=False
        )

    click.echo(
        click.style(
            'Installation complete! Run "footing shell" to use footing.',
            fg="green",
        )
    )
