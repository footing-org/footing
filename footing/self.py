"""Methods that operate on the footing executable"""
import contextlib
import subprocess

import footing.utils


def init(system=False):
    """Initialize footing after the script-based installation
    
    Args:
        system (bool, optional): True if footing should be installed in the /usr/local/bin
            directory.
    """
    micromamba_path = footing.utils.micromamba_path()
    if not footing.utils.micromamba_path().exists():
        raise RuntimeError("No conda installation found. Please use the official installer.")

    condabin_path = footing.utils.condabin_path()
    condabin_path.mkdir(exist_ok=True)

    # Create soft links to footing so that it is globally installed among envs
    with contextlib.chdir(condabin_path):
        footing.utils.shell(
            "ln -sf ../bin/footing footing",
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    if system:
        print(
            footing.utils.style(
                "Enter your password if prompted to install footing in /usr/local/bin/.",
                color="green",
            )
        )
        footing.utils.shell(
            f"sudo ln -sf {footing.utils.footing_path()} /usr/local/bin/footing",
            check=False,
        )

    print(
        footing.utils.style(
            'Installation complete! Run "footing shell" to use footing.',
            color="green",
        )
    )
