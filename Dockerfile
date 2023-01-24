ARG BASE_IMAGE=debian:bullseye-slim

# Mutli-stage build to keep final image small. Otherwise end up with
# curl and openssl installed
FROM --platform=$BUILDPLATFORM $BASE_IMAGE AS builder
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN apt-get update && apt-get install -y --no-install-recommends \
    bzip2 \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt /var/lib/dpkg /var/lib/cache /var/lib/log
RUN mkdir /footing
ENV FOOTING_SELF_INIT_NO_SHELL_INTEGRATION=1 FOOTING_SELF_INIT_NO_SYSTEM=1 FOOTING_BRANCH=mvp PREFIX=/footing
RUN curl https://raw.githubusercontent.com/wesleykendall/footing/mvp/install.sh | /bin/bash
RUN rm -rf /footing/toolkits/pkgs

# Final image
FROM $BASE_IMAGE

RUN mkdir /project
WORKDIR /project
ENV PATH=/footing/toolkits/bin:$PATH

COPY --from=builder /etc/ssl/certs/ca-certificates.crt /etc/ssl/certs/ca-certificates.crt
COPY --from=builder /footing /footing
ENTRYPOINT ["footing"]
