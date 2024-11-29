#!/usr/bin/env bash
set -eux
cd "${0%/*}"
CONTAINER_NAME="test_qcow2target_iscsi"
export TEST_IMAGE=qcowtargettest
export BINARIES_DIR=/opt
docker build -t "${TEST_IMAGE}" --build-arg "INNER_BINARIES_DIR=${BINARIES_DIR}" -f docker/iscsi_test/Dockerfile .
docker rm -f "${CONTAINER_NAME}"
docker run  --name "${CONTAINER_NAME}" -t $TEST_IMAGE
docker cp "${CONTAINER_NAME}:${BINARIES_DIR}/tgt.log" /tmp/tgt.log
docker rm -f "${CONTAINER_NAME}"
