#!/bin/sh

###
# Install mambaforge
###

conda_ver=22.9.0
footing_ver=0.1.6
mambaforge_patch=2

if [ "$(uname)" == "Darwin" ]; then
    mamba_platform=MacOSX
elif [ "$(uname)" == "Linux" ]; then
    mamba_platform=Linux
else
    printf "Unsupported OS\\n"
    exit 2
fi

case $(uname -m) in
    aarch64|ppc64le|x86_64|arm64)
        export mamba_arch=$(uname -m)
        ;;
    *)
        printf "Unsupported architecture\\n"
        exit 2
esac

mamba_installer_url=https://github.com/conda-forge/miniforge/releases/download/${conda_ver}-${mambaforge_patch}/Mambaforge-${conda_ver}-${mambaforge_patch}-${mamba_platform}-${mamba_arch}.sh
mamba_installer_dir=$(mktemp -d)
mamba_installer_file="$mamba_installer_dir/install.sh"
curl -L $mamba_installer_url -o $mamba_installer_file --progress-bar
sh $mamba_installer_file -p $HOME/.footing/conda -b -u

###
# Install footing
###

footing_wheel="footing-${footing_ver}-py3-none-any.whl"
footing_package_url="https://raw.githubusercontent.com/wesleykendall/footing/main/install/${footing_wheel}"
footing_package_dir=$(mktemp -d)
footing_package_file="$footing_package_dir/${footing_wheel}"
curl -L $footing_package_url -o $footing_package_file --progress-bar
$HOME/.footing/conda/bin/pip3 install $footing_package_file
$HOME/.footing/conda/bin/footing bootstrap
