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


def bootstrap():
    """Bootstraps footing's internal dependencies and finalizes installation"""
    footing_file_path = footing.version.metadata.distribution("footing").files[0]
    site_packages_dir = pathlib.Path(
        str(footing_file_path.locate())[: -len(str(footing_file_path))]
    )
    condabin_dir = site_packages_dir / ".." / ".." / ".." / "condabin"

    if not condabin_dir.exists():
        raise RuntimeError("Footing is not installed properly. Please use the official installer")

    if not str(condabin_dir).startswith(str(footing.util.conda_dir())):
        raise RuntimeError(
            "Footing is installed in the wrong location. Please use the official installer"
        )

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
            'Installation complete! Click "Enter" to run "footing shell" for the first time.',
            fg="green",
        )
    )
    input()
