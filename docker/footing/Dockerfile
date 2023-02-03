# Final image
FROM footingorg/core

# This is to help with layer caching and faster deployments for now. In the future we may place this in one layer
ADD *.whl .
RUN pip3 install --upgrade --force-reinstall *.whl && FOOTING_SELF_INIT_NO_SHELL_INTEGRATION=1 FOOTING_SELF_INIT_NO_SYSTEM=1 footing self init
