FROM footingorg/footing

RUN apt-get update && apt-get install -y --no-install-recommends \
    bzip2 \
    curl \
    jq

RUN micromamba -r /footing/toolkits/ install kubernetes-client pyyaml -n base -c conda-forge -y && \
    rm -rf /footing/toolkits/pkgs

RUN useradd -m footing
WORKDIR /home

COPY docker/actions/download.sh download.sh

RUN mkdir /home/footing/actions-runner && cd /home/footing/actions-runner && bash /home/download.sh
RUN chown -R footing ~footing && /home/footing/actions-runner/bin/installdependencies.sh
RUN chown -R footing /footing

COPY docker/actions/start.sh start.sh
RUN chmod +x start.sh

USER footing

ENTRYPOINT ["./start.sh"]
