#!/usr/bin/env bash

set -eux
cd "${0%/*}"

export CONTAINER_NAME="qcow2targetbuildercontainer"
export TEST_IMAGE="qcow2targetbuilderimage"
export FINAL_PACKAGE_DIR="/opt/debian_package"

docker build -t "${TEST_IMAGE}" --build-arg "_FINAL_PACKAGE_DIR=${FINAL_PACKAGE_DIR}" -f docker/debian_builder/Dockerfile .

CONTAINER_ID=$(docker container ls -a --filter name="${CONTAINER_NAME}" -q)
if [ -n "${CONTAINER_ID}" ]; then
  if [ "$( docker container inspect -f '{{.State.Running}}' "${CONTAINER_ID}" )" == "true" ]; then
    docker kill "{$CONTAINER_ID}" || echo "Failed to kill running container from previous build"
  fi
  docker rm "${CONTAINER_ID}" || echo "container does not exists"
fi


docker run  --name "${CONTAINER_NAME}" -t $TEST_IMAGE
docker cp "${CONTAINER_NAME}:${FINAL_PACKAGE_DIR}" .