FROM ubuntu

RUN apt-get update && apt-get install -y curl

RUN sh -c 'curl https://raw.githubusercontent.com/wesleykendall/footing/main/install.sh | bash'