FROM ubuntu AS builder

RUN apt-get update && apt-get install -y curl bzip2
RUN mkdir /footing
RUN sh -c 'curl https://raw.githubusercontent.com/wesleykendall/footing/mvp/install.sh | FOOTING_BRANCH=mvp PREFIX=/footing bash'

FROM alpine:latest  
COPY --from=builder /footing /footing
ENV PATH=/root/.footing/toolkits/bin:$PATH
