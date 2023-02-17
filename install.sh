#!/bin/sh
set -e

footing_ver="${FOOTING_VERSION:-1.0.0}"
footing_maj_ver=(${footing_ver//./ })
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
micromamba_prefix=$footing_prefix/v$footing_maj_ver

printf "\033[0;32mInstalling micromamba...\033[0m\\n"
download_file $micromamba_installer_url $micromamba_archive_file
mkdir -p $micromamba_prefix/bin
cat $micromamba_archive_file | tar -xj -C $micromamba_prefix/bin --strip-components=1 bin/micromamba

###
# Install python
###

printf "\033[0;32mInstalling python...\033[0m\\n"
$micromamba_prefix/bin/micromamba -r $micromamba_prefix -y --no-rc --no-env install python==3.11 -c conda-forge -n base

###
# Install footing
###

footing_branch="${FOOTING_BRANCH:-main}"
footing_wheel="footing-$footing_ver-py3-none-any.whl"
footing_package_url="https://raw.githubusercontent.com/footing-org/footing/$footing_branch/$footing_wheel"
footing_package_dir=$(mktemp -d)
footing_package_file="$footing_package_dir/$footing_wheel"

printf "\033[0;32mInstalling footing... \033[0m\\n"
download_file $footing_package_url $footing_package_file
$micromamba_prefix/bin/pip3 install --upgrade --force-reinstall $footing_package_file
$micromamba_prefix/bin/footing self init
