#!/usr/bin/env bash
set -eux
cd "${0%/*}"

# A list of early boot scripts. Seems to be useless. Attempts to do some dpkg-reconfigure.
systemctl stop nvfb-early.service
systemctl disable nvfb-early.service
systemctl stop nvfb.service
systemctl disable nvfb.service

# A service trying to configure NVIDIA-weston
# See: https://github.com/microcai/nvidia-weston/blob/master/README
systemctl stop nv.service
systemctl disable nv.service
systemctl stop nvweston.service
systemctl disable nvweston.service

# Disable Nvidia Power Model Tool
systemctl stop nvpmodel.service
systemctl disable nvpmodel.service

# A service configuring a virtual network for remote access via USB interface. It is not needed for FT purposes.
systemctl stop nv-l4t-usb-device-mode.service
systemctl disable nv-l4t-usb-device-mode.service
systemctl mask nv-l4t-usb-device-mode-runtime-start.service

# A camera-controlling service. It is not needed for FT purposes.
# See: https://github.com/NVIDIA-AI-IOT/argus_camera
systemctl stop nvargus-daemon.service
systemctl disable nvargus-daemon.service

# Prints some warnings at low memory
systemctl stop nvmemwarning.service
systemctl disable nvmemwarning.service

# Quote: L4T system setup and general setup for thermal zones. It is unclear what the service does.
systemctl stop nvphs.service
systemctl disable nvphs.service

# NVS-SERVICE Embedded Sensor HAL Daemon
systemctl stop nvs-service.service
systemctl disable nvs-service.service

# Unused Wi-fi controller service.
systemctl stop wpa_supplicant.service
systemctl mask wpa_supplicant.service

# Disable NVIDIA WiFi-BT config service
systemctl stop nvwifibt.service
systemctl disable nvwifibt.service

# Disable End-user configuration after initial OEM installation
systemctl stop nv-oem-config-debconf@nvfb-early.service
systemctl mask nv-oem-config-debconf@nvfb-early.service
systemctl stop nv-oem-config-debconf@nvweston.service
systemctl mask nv-oem-config-debconf@nvweston.service
systemctl stop nv-oem-config-gui.service
systemctl mask nv-oem-config-gui.service

systemctl stop apt-daily-upgrade.timer
systemctl mask apt-daily-upgrade.timer
systemctl stop apt-daily-upgrade.service
systemctl mask apt-daily-upgrade.service

systemctl stop apt-daily.timer
systemctl mask apt-daily.timer
systemctl stop apt-daily.service
systemctl mask apt-daily.service

systemctl stop motd-news.timer
systemctl mask motd-news.timer
systemctl stop motd-news.service
systemctl mask motd-news.service

systemctl stop fstrim.timer
systemctl mask fstrim.timer
systemctl stop fstrim.service
systemctl mask fstrim.service

systemctl stop anacron.timer
systemctl mask anacron.timer
systemctl stop anacron.service
systemctl mask anacron.service

systemctl stop iscsid.service
systemctl mask iscsid.service

systemctl stop iscsid.socket
systemctl mask iscsid.socket

systemctl stop docker.socket
systemctl stop docker.service
systemctl mask docker.socket
systemctl mask docker.service

systemctl stop avahi-daemon.socket
systemctl mask avahi-daemon.socket
systemctl stop avahi-daemon.service
systemctl mask avahi-daemon.service

systemctl stop gpsd.socket
systemctl mask gpsd.socket

systemctl mask ubuntu-fan.service

systemctl daemon-reload

apt -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false update

DEBIAN_FRONTEND=noninteractive apt purge -y bolt

DEBIAN_FRONTEND=noninteractive apt install -y \
gdb \
tshark \
tcpdump \
smbclient \
samba \
unzip \
cifs-utils \
zlib1g \
debconf \
net-tools \
file \
libglu1-mesa \
libopenal-data \
libopenal1 \
libsecret-1-0 \
libsecret-common \
libxcursor1 \
libxrandr2 \
libxss1 \
libxtst6 \
libpulse-mainloop-glib0 \
libpulse0 \
libxi6 \
libxcomposite1 \
libxt6 \
liborc-0.4-0 \
libnss3 \
libasound2 \
libegl1-mesa \
libxcb-icccm4 \
libxcb-image0 \
libxcb-keysyms1 \
libxcb-randr0 \
libxcb-render-util0 \
libxcb-shape0 \
libxcb-util1 \
libxcb-xinerama0 \
libxcb-xkb1 \
libxcb-icccm4 \
libxcb-image0 \
libxcb-keysyms1 \
libxcb-randr0 \
libxcb-render-util0 \
libxcb-shape0 \
libxcb-xinerama0 \
libxcb-xkb1 \
libxrender1 \
libxfixes3 \
libfontconfig1 \
libsm6 \
libice6 \
libaudio2 \
libgl1-mesa-glx \
libxslt1.1 \
libxkbcommon0 \
xvfb \
imagemagick \
mesa-utils \
tgt \
iptables \
psmisc \
man \
htop \
strace \
language-pack-ru \
lsof \
open-iscsi

rm -f /lib/modules-load.d/open-iscsi.conf

systemctl enable systemd-networkd


cat <<EOF >/etc/systemd/network/60-eth0.network
[Match]
Name=eth0

[Network]
DHCP=yes
IgnoreCarrierLoss=true
EOF
