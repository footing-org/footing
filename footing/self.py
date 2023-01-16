"""Methods that operate on the footing executable"""
import contextlib
import subprocess

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
            shell_integration = footing.utils.confirm_prompt(
                footing.utils.style("Install shell integration?", color="green"), default="y"
            )

        # Initialize shell integration
        if shell_integration:
            footing.shell.init()

    if not no_system and not no_prompt:
        print(
            footing.utils.style(
                "Enter your password if prompted to install footing in /usr/local/bin/.",
                color="green",
            )
        )
        retry_system = True
        while retry_system:
            try:
                footing.utils.run(
                    f"sudo ln -sf {footing.utils.footing_path()} /usr/local/bin/footing",
                    check=True,
                )
                retry_system = False
            except subprocess.CalledProcessError:
                retry_system = footing.utils.confirm_prompt(
                    footing.utils.style("Try again?", color="green"),
                    default="y",
                )

    print(
        footing.utils.style(
            'Installation complete! Run "footing shell" to use footing.',
            color="green",
        )
    )
