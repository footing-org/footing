"""
footing.bootstrap
~~~~~~~~~~~~~~~~~

Bootstraps footing's internal dependencies
"""
import subprocess

import click

import footing.util
import footing.version


def bootstrap(system=False):
    """Bootstraps footing's internal dependencies and finalizes installation"""
    condabin_dir = footing.util.condabin_dir(check=True)

    base_libraries = [
        "git==2.39.0",
        "conda-lock==1.3.0",
        "lockfile==0.12.2",
        "conda-pack==0.7.0",
        "squashfs-tools==4.4",
        "docker-py==6.0.0",
    ]
    all_libraries = base_libraries + ["terraform==1.3.5"]

    try:
        # Try to install all libraries at first.
        footing.util.conda("install -q -n base -y " + " ".join(all_libraries))
    except Exception:
        # Some architectures don't support terraform, so ignore it for now
        footing.util.conda("install -q -n base -y " + " ".join(base_libraries))

    # Create soft links to global tools in the conda bin dir
    with footing.util.cd(condabin_dir):
        footing.util.shell(
            "ln -sf ../bin/footing footing",
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        footing.util.shell(
            "ln -sf ../bin/git git",
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
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
            f"sudo ln -sf {footing.util.footing_exe()} /usr/local/bin/footing",
            check=False,
        )

    click.echo(
        click.style(
            'Installation complete! Run "footing shell" to use footing.',
            fg="green",
        )
    )
