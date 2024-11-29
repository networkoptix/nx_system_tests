BIN_DIR?="build"
BINARY_NAME?="qcow2target"
ADMIN_BINARY_NAME?="qcow2targetadmin"
TMP=tests_tmp

all: init deps build admin_build

deps:
	go mod download

build:
	go build -o ${BIN_DIR}/${BINARY_NAME} main.go

admin_build:
	go build -o ${BIN_DIR}/${ADMIN_BINARY_NAME} client.go

init:
	mkdir -p ${BIN_DIR}
clean:
	rm -rf ${BIN_DIR}

test_init:
	mkdir -p ${TMP}
test_clean:
	rm -rf ${TMP}
test_exec:
	TMPDIR=${TMP} go test -timeout 30m qcow2target/pkg/qcow2

test: deps test_clean test_init test_exec

.PHONY: all build admin_build test_exec test