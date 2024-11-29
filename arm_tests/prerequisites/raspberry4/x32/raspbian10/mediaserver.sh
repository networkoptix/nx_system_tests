#!/usr/bin/env bash
set -eux
cd "${0%/*}"

apt -o DPkg::Lock::Timeout=120 -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false update

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
lsof \
open-iscsi
