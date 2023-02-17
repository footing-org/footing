"""Methods that operate on the footing executable"""
import contextlib
import subprocess

import footing.cli
import footing.shell
import footing.utils


def init(no_system=False, no_prompt=False, no_shell_integration=False):
    """Initialize footing after the script-based installation

    Args:
        no_system (bool, default=False): Turn off system-wide installation
        no_prompt (bool, default=False): Turn off prompting user for input
        no_shell_integration (bool, default=False): Disable shell integration
    """
    micromamba_path = footing.utils.micromamba_path()
    if not footing.utils.micromamba_path().exists():
        raise RuntimeError("No conda installation found. Please use the official installer.")

    condabin_path = footing.utils.condabin_path()
    condabin_path.mkdir(exist_ok=True)

    # Create soft links to footing so that it is globally installed among envs
    with contextlib.chdir(condabin_path):
        footing.utils.run(
            "ln -sf ../bin/footing footing",
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    if not no_shell_integration:
        shell_integration = True
        if not no_prompt:
            shell_integration = footing.cli.confirm_prompt(
                "Install shell integration?", default="y", color="green"
            )

        # Initialize shell integration
        if shell_integration:
            footing.shell.init()

    if not no_system and not no_prompt:
        footing.cli.pprint(
            "Enter your password if prompted to install footing in /usr/local/bin/.",
        )

        retry_system = True
        while retry_system:
            try:
                footing.utils.run(
                    f"sudo ln -sf {footing.utils.footing_path()} /usr/local/bin/footing",
                    check=True,
                )
                footing.utils.run(
                    f"sudo ln -sf {footing.utils.footing_path()} /usr/local/bin/f",
                    check=True,
                )
                retry_system = False
            except subprocess.CalledProcessError:
                retry_system = footing.cli.confirm_prompt(
                    "Try again?",
                    default="y",
                )

    footing.cli.pprint(
        "Installation complete! Restart your shell to use footing.",
        color="green",
    )
