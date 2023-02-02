FROM footingorg/footing

RUN micromamba -r /footing/toolkits/ install git rsync -n base -c conda-forge -y && \
    rm -rf /footing/toolkits/pkgs
