#!/bin/bash

set -eux
cd "${0%/*}" || exit # cd to script directory
cd ../../ # cd to project root

FINAL_PACKAGE_DIR=${1:?The first argument must be a final package directory}
BINARY_NAME="qcow2target"
PACKAGE_VERSION="$(date +%y%m%d%H%M%S)"

BUILD_DIR="build"
ADMIN_BINARY_NAME="qcow2targetadmin"

PACKAGE_NAME=${BINARY_NAME}
PACKAGE_DIR="${PACKAGE_NAME}_${PACKAGE_VERSION}_amd64"

REQUIRED_PACKAGE_USERNAME="${PACKAGE_NAME}user"
REQUIRED_GROUP="${PACKAGE_NAME}group"

SERVICE_NAME="${PACKAGE_NAME}_server.service"
SERVICE_DIR="/etc/systemd/system/"
SERVICE_PATH="${SERVICE_DIR}${SERVICE_NAME}"
BINARY_DESTINATION_DIR="/usr/local/bin/"
BINARY_DESTINATION_PATH="${BINARY_DESTINATION_DIR}${BINARY_NAME}"

make clean
make

mkdir -p "${PACKAGE_DIR}/DEBIAN"
mkdir -p "${PACKAGE_DIR}${BINARY_DESTINATION_DIR}"
mkdir -p "${PACKAGE_DIR}${SERVICE_DIR}"

export PACKAGE_NAME \
  SERVICE_PATH \
  BINARY_DESTINATION_PATH \
  REQUIRED_PACKAGE_USERNAME \
  REQUIRED_GROUP \
  SERVICE_NAME \
  PACKAGE_VERSION

# Redundant shellcheck here,
# since we need to use $ in envsubst command
# shellcheck disable=SC2016
EXPORTED_VARS='$PACKAGE_NAME '\
'$SERVICE_PATH '\
'$BINARY_DESTINATION_PATH '\
'$REQUIRED_PACKAGE_USERNAME '\
'$REQUIRED_GROUP '\
'$SERVICE_NAME '\
'$PACKAGE_VERSION '

envsubst "${EXPORTED_VARS}" < packaging/ubuntu/debian/postinst > "${PACKAGE_DIR}/DEBIAN/postinst"
envsubst "${EXPORTED_VARS}" < packaging/ubuntu/debian/prerm > "${PACKAGE_DIR}/DEBIAN/prerm"
envsubst "${EXPORTED_VARS}" < packaging/ubuntu/debian/postrm > "${PACKAGE_DIR}/DEBIAN/postrm"
envsubst "${EXPORTED_VARS}" < packaging/ubuntu/debian/control > "${PACKAGE_DIR}/DEBIAN/control"
envsubst "${EXPORTED_VARS}" < packaging/target.service > "${PACKAGE_DIR}${SERVICE_PATH}"

chmod 755 "${PACKAGE_DIR}/DEBIAN/postinst"
chmod 755 "${PACKAGE_DIR}/DEBIAN/prerm"
chmod 755 "${PACKAGE_DIR}/DEBIAN/postrm"

cp "${BUILD_DIR}/${BINARY_NAME}" "${PACKAGE_DIR}${BINARY_DESTINATION_PATH}"
cp "${BUILD_DIR}/${ADMIN_BINARY_NAME}" "${PACKAGE_DIR}${BINARY_DESTINATION_DIR}${ADMIN_BINARY_NAME}"
mkdir "${FINAL_PACKAGE_DIR}"
dpkg-deb --build --root-owner-group "${PACKAGE_DIR}"
cp "${PACKAGE_DIR}.deb" "${FINAL_PACKAGE_DIR}"