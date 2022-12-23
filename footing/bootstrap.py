"""
footing.bootstrap
~~~~~~~~~~~~~~~~~

Bootstraps footing's internal dependencies
"""
import os
import platform
import subprocess
import tempfile

import requests
from tqdm import tqdm

import footing.util


def bootstrap():
    """Bootstraps footing's internal dependencies"""

    os_name = platform.system()
    os_name = "MacOSX" if os_name == "Darwin" else os_name
    machine = platform.machine().lower().split(" ")[0]
    machine = "x86_64" if machine == "amd64" else machine
    arch = f"{os_name}-{machine}"

    if arch not in [
        "MacOSX-arm64",
        "Windows-x86_64",
        "MacOSX-x86_64",
        "Linux-x86_64",
        "Linux-s390x",
        "Linux-aarch64",
        "Linux-ppc64le",
    ]:
        raise RuntimeError(f"{arch} not a supported architecture")

    conda_ver = "4.14.0"
    ext = "exe" if os_name == "Windows" else "sh"

    with tempfile.TemporaryDirectory() as tmpdir:
        # Miniconda installer
        # url = (
        #     f"https://repo.anaconda.com/miniconda/Miniconda3-{python_ver}_{conda_ver}-{arch}.{ext}"
        # )

        # Mambaforge installer
        url = (
            "https://github.com/conda-forge/miniforge/releases/download/"
            f"{conda_ver}-2/Mambaforge-{conda_ver}-2-{arch}.{ext}"
        )
        filename = os.path.join(tmpdir, "miniconda_installer.sh")

        if not os.path.exists(filename):
            r = requests.get(url, stream=True)
            with open(filename, "wb") as f:
                pbar = tqdm(
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    total=int(r.headers["Content-Length"]),
                )
                for chunk in r.iter_content(chunk_size=1024):
                    if chunk:  # filter out keep-alive new chunks
                        pbar.update(len(chunk))
                        f.write(chunk)
                pbar.close()

        conda_dir = footing.util.conda_dir()
        run_cmd = f"{filename} -p {conda_dir} -b -u"
        if os_name != "Windows":
            run_cmd = f"sh {run_cmd}"

        subprocess.run(run_cmd, shell=True)
