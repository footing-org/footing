#!/bin/sh
set -e

default_footing_prefix=$HOME/.footing
footing_prefix="${PREFIX:-$default_footing_prefix}" 

###
# Install mambaforge
###

mamba_ver=22.9.0
footing_ver=0.1.7
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

mamba_prefix=$footing_prefix/toolkits
mamba_installer_url=https://github.com/conda-forge/miniforge/releases/download/$mamba_ver-$mambaforge_patch/Mambaforge-$mamba_ver-$mambaforge_patch-$mamba_platform-$mamba_arch.sh
mamba_installer_dir=$(mktemp -d)
mamba_installer_file="$mamba_installer_dir/install.sh"

if command -v curl &> /dev/null
then
    curl -L $mamba_installer_url -o $mamba_installer_file --progress-bar
elif command -v python3 &> /dev/null
then
    printf "Downloading mamba installer..."
    python3 -c "import urllib.request; urllib.request.urlretrieve('$mamba_installer_url', '$mamba_installer_file')"
else
    printf "Need curl or python3 to complete installation\\n"
    exit 2
fi

if [ -z "$FOOTING_INSTALL_SKIP_MAMBA" ]
then
    sh $mamba_installer_file -p $mamba_prefix -b -u
fi

###
# Install footing
###

footing_wheel="footing-$footing_ver-py3-none-any.whl"
footing_package_url="https://raw.githubusercontent.com/wesleykendall/footing/main/$footing_wheel"
footing_package_dir=$(mktemp -d)
footing_package_file="$footing_package_dir/$footing_wheel"

if command -v curl &> /dev/null
then
    curl -L $footing_package_url -o $footing_package_file --progress-bar
elif command -v python3 &> /dev/null
then
    printf "Downloading footing wheel..."
    python3 -c "import urllib.request; urllib.request.urlretrieve('$footing_package_url', '$footing_package_file')"
else
    printf "Need curl or python3 to complete installation\\n"
    exit 2
fi

$mamba_prefix/bin/pip3 install --upgrade --force-reinstall $footing_package_file

if [ -z "$FOOTING_BOOTSTRAP_SKIP_SYSTEM" ]
then
    $mamba_prefix/bin/footing bootstrap --system
else
    $mamba_prefix/bin/footing bootstrap
fi
