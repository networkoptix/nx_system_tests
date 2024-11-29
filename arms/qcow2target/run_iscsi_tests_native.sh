#!/usr/bin/env bash
set -eux
cd "${0%/*}"
export BIN_DIR="build"
export BINARY_NAME="qcow2target"
export ADMIN_BINARY_NAME="qcow2targetadmin"
make clean
make
bash test/libiscsi-test.sh "${BIN_DIR}/${BINARY_NAME}" "${ADMIN_BINARY_NAME}" || echo "Tests failed"
