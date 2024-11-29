#!/usr/bin/env bash
set -eux
cd "${0%/*}"

# DHCP protocol is used in the FT environment.
systemctl stop avahi-daemon.socket
systemctl disable avahi-daemon.socket
systemctl stop avahi-daemon.service
systemctl disable avahi-daemon.service

# A service configuring a virtual network for remote access via USB interface. It is not needed for FT purposes.
systemctl stop nv-l4t-usb-device-mode.service
systemctl disable nv-l4t-usb-device-mode.service

# A camera-controlling service. It is not needed for FT purposes.
# See: https://github.com/NVIDIA-AI-IOT/argus_camera
systemctl stop nvargus-daemon.service
systemctl disable nvargus-daemon.service

# Quote: L4T system setup and general setup for thermal zones. It is unclear what the service does.
systemctl stop nvphs.service
systemctl disable nvphs.service

# NVS-SERVICE Embedded Sensor HAL Daemon.
systemctl stop nvs-service.service
systemctl disable nvs-service.service

systemctl stop apt-daily-upgrade.timer
systemctl disable apt-daily-upgrade.timer
systemctl stop apt-daily-upgrade.service
systemctl disable apt-daily-upgrade.service

systemctl stop apt-daily.timer
systemctl disable apt-daily.timer
systemctl stop apt-daily.service
systemctl disable apt-daily.service

systemctl stop dpkg-db-backup.timer
systemctl disable dpkg-db-backup.timer
systemctl disable dpkg-db-backup.service

systemctl stop fwupd-refresh.timer
systemctl disable fwupd-refresh.timer
systemctl disable fwupd-refresh.service

systemctl stop logrotate.timer
systemctl disable logrotate.timer
systemctl disable logrotate.service

systemctl stop man-db.timer
systemctl disable man-db.timer
systemctl disable man-db.service

systemctl stop motd-news.timer
systemctl disable motd-news.timer
systemctl disable motd-news.service

systemctl stop systemd-tmpfiles-clean.timer
systemctl disable systemd-tmpfiles-clean.timer
systemctl disable systemd-tmpfiles-clean.service

systemctl stop update-notifier-download.timer
systemctl disable update-notifier-download.timer
systemctl disable update-notifier-download.service

systemctl stop update-notifier-motd.timer
systemctl disable update-notifier-motd.timer
systemctl disable update-notifier-motd.service

systemctl stop e2scrub_all.timer
systemctl disable e2scrub_all.timer
systemctl disable e2scrub_all.service

systemctl daemon-reload

apt -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false update

# System daemon to manage thunderbolt 3 devices.
DEBIAN_FRONTEND=noninteractive apt purge -y bolt

DEBIAN_FRONTEND=noninteractive apt install -y \
tshark \
cifs-utils \
debconf \
file \
libcap2-bin \
libexpat1 \
net-tools \
zlib1g \
libglib2.0-0

rm -f /lib/modules-load.d/open-iscsi.conf
