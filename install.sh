#!/bin/sh
set -e

default_footing_prefix=$HOME/.footing
footing_prefix="${PREFIX:-$default_footing_prefix}"
mkdir -p $footing_prefix

download_file() {
    if command -v curl &> /dev/null
    then
        curl -L $1 -o $2 --progress-bar
    elif command -v python3 &> /dev/null
    then
        python3 -c "import urllib.request; urllib.request.urlretrieve('$1', '$2')"
    else
        printf "Need curl or python3 to complete installation\\n"
        exit 2
    fi
}

###
# Install micromamba
###

arch=$(uname -m)
os=$(uname)

if [[ "$os" == "Linux" ]]; then
	platform="linux"
	if [[ "$arch" == "aarch64" ]]; then
		arch="aarch64";
	elif [[ $arch == "ppc64le" ]]; then
		arch="ppc64le";
	else
		arch="64";
	fi		
elif [[ "$os" == "Darwin" ]]; then
	platform="osx";
	if [[ "$arch" == "arm64" ]]; then
		arch="arm64";
	else
		arch="64"
	fi
else
    printf "Unsupported architecture\\n"
    exit 2
fi

micromamba_installer_dir=$(mktemp -d)
micromamba_archive_file="$micromamba_installer_dir/micromamba.tar.gz"
micromamba_installer_url="https://micro.mamba.pm/api/micromamba/$platform-$arch/latest"
micromamba_prefix=$footing_prefix/toolkits

printf "Installing micromamba...\\n"
download_file $micromamba_installer_url $micromamba_archive_file
mkdir -p $footing_prefix/toolkits/bin
cat $micromamba_archive_file | tar -xj -C $footing_prefix/toolkits/bin --strip-components=1 bin/micromamba

###
# Install python
###

printf "Installing python...\\n"

$micromamba_prefix/bin/micromamba -r $micromamba_prefix install -y python==3.11 -c conda-forge

###
# Install footing
###

footing_ver="${FOOTING_BRANCH:-1.0.0}"
footing_branch="${FOOTING_BRANCH:-main}"
footing_wheel="footing-$footing_ver-py3-none-any.whl"
footing_package_url="https://raw.githubusercontent.com/wesleykendall/footing/$footing_branch/$footing_wheel"
footing_package_dir=$(mktemp -d)
footing_package_file="$footing_package_dir/$footing_wheel"

printf "Installing footing...\\n"
download_file $footing_package_url $footing_package_file

$footing_prefix/toolkits/bin/pip3 install --upgrade --force-reinstall $footing_package_file

if [[ -z "$FOOTING_BOOTSTRAP_SKIP_SYSTEM" ]]
then
    $footing_prefix/bin/footing bootstrap --system
else
    $footing_prefix/bin/footing bootstrap
fi
