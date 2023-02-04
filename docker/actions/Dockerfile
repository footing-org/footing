FROM debian:bullseye-slim AS builder

RUN apt-get update && apt-get upgrade && apt-get install -y --no-install-recommends \
    bzip2 \
    ca-certificates \
    curl \
    jq

# Download and install github runner
COPY docker/actions/download.sh /home/download.sh
RUN useradd -m footing
RUN mkdir /home/footing/actions-runner && cd /home/footing/actions-runner && bash /home/download.sh
RUN chown -R footing ~footing && /home/footing/actions-runner/bin/installdependencies.sh

# Final image
FROM footingorg/core

COPY --from=builder / /

RUN micromamba -r /footing/toolkits/ install kubernetes-client pyyaml rsync -n base -c conda-forge -y && \
    rm -rf /footing/toolkits/pkgs
RUN chown -R footing /footing

# Copy the script for starting the runner
COPY docker/actions/start.sh start.sh
RUN chmod +x start.sh

# Must run as non-root for github actions
USER footing

# This is to help with layer caching and faster deployments for now. In the future we may place this in one layer
ADD *.whl .
RUN pip3 install --upgrade --force-reinstall *.whl && FOOTING_SELF_INIT_NO_SHELL_INTEGRATION=1 FOOTING_SELF_INIT_NO_SYSTEM=1 footing self init

ENTRYPOINT ["./start.sh"]
