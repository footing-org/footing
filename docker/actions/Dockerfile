FROM footingorg/footing:latest AS builder

ARG RUNNER_VERSION="2.299.2"

RUN apt-get update && apt-get install -y --no-install-recommends \
    bzip2 \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt /var/lib/dpkg /var/lib/cache /var/lib/log

RUN /footing/toolkits/bin/micromamba -r /footing/toolkits/ install jq -n base -c conda-forge -y
RUN useradd footing

RUN cd /home/footing && mkdir actions-runner && cd actions-runner \
    && curl -O -L https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz \
    && tar xzf ./actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz


    # Mutli-stage build to keep final image small. Otherwise end up with
# curl and openssl installed
FROM $BASE_IMAGE AS builder

RUN mkdir /footing
ENV FOOTING_SELF_INIT_NO_SHELL_INTEGRATION=1 FOOTING_SELF_INIT_NO_SYSTEM=1 FOOTING_BRANCH=mvp PREFIX=/footing
RUN curl https://raw.githubusercontent.com/footing-org/footing/mvp/install.sh | /bin/bash
RUN /footing/toolkits/bin/micromamba -r /footing/toolkits/ install git rsync -n base -c conda-forge -y
RUN rm -rf /footing/toolkits/pkgs