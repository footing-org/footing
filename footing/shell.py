import footing.utils


def init(shell=None):
    shell = shell or footing.utils.detect_shell()
    if not shell:
        raise RuntimeError("Could not detect shell. Use --shell argument")

    footing.utils.conda_cmd(f"shell init -p {footing.utils.conda_root_path()} -s {shell}")
