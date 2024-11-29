FROM ubuntu:focal

ARG INNER_BINARIES_DIR
ENV BIN_DIR=$INNER_BINARIES_DIR
ENV TEST_SCRIPT=$BIN_DIR/test.sh
ENV BINARY_NAME=qcow2target
ENV ADMIN_BINARY_NAME=qcow2targetadmin
ENV INNER_BIN_PATH=$BIN_DIR/$BINARY_NAME
ENV PATH="${PATH}:/usr/local/go/bin"

RUN apt-get -y update && apt-get -y install libiscsi-bin make curl
RUN curl -OL https://go.dev/dl/go1.18.4.linux-amd64.tar.gz
RUN tar -C /usr/local -xzf go1.18.4.linux-amd64.tar.gz

ADD . $BIN_DIR/project
RUN bash -c "cd $BIN_DIR/project && make"

COPY test/libiscsi-test.sh $TEST_SCRIPT

RUN chmod +x $INNER_BIN_PATH
RUN chmod +x $BIN_DIR/$ADMIN_BINARY_NAME
RUN chmod +x $TEST_SCRIPT

ENTRYPOINT $BIN_DIR/test.sh $INNER_BIN_PATH $ADMIN_BINARY_NAME
