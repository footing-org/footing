#!/bin/sh
runner_version="2.301.1"

arch=$(uname -m)
os=$(uname)

if [[ "$os" == "Linux" ]]; then
	platform="linux"
	if [[ "$arch" == "aarch64" ]]; then
		arch="arm64";
	else
		arch="x64";
	fi
else
    printf "Unsupported architecture\\n"
    exit 2
fi

curl -O -L https://github.com/actions/runner/releases/download/v${runner_version}/actions-runner-${platform}-${arch}-${runner_version}.tar.gz \
    && tar xzf ./actions-runner-${platform}-${arch}-${runner_version}.tar.gz
