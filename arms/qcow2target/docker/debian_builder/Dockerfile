FROM ubuntu:focal

RUN apt-get -y update && apt-get -y install make curl gettext-base
RUN curl -OL https://go.dev/dl/go1.18.4.linux-amd64.tar.gz
RUN tar -C /usr/local -xzf go1.18.4.linux-amd64.tar.gz

ARG _FINAL_PACKAGE_DIR
ENV FINAL_PACKAGE_DIR $_FINAL_PACKAGE_DIR
ENV PROJECT_DIR /opt/project/
ENV BUILDER_PATH packaging/ubuntu/build_debian_package.sh
ENV PATH="${PATH}:/usr/local/go/bin"
ADD . $PROJECT_DIR

RUN chmod +x $PROJECT_DIR$BUILDER_PATH
ENTRYPOINT $PROJECT_DIR$BUILDER_PATH $FINAL_PACKAGE_DIR