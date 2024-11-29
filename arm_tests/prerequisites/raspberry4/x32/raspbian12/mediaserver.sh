#!/usr/bin/env bash
set -eux
cd "${0%/*}"

apt -o DPkg::Lock::Timeout=120 -o Acquire::Check-Valid-Until=false -o Acquire::Check-Date=false update

DEBIAN_FRONTEND=noninteractive apt install -y \
gdb \
tshark \
tcpdump \
unzip \
cifs-utils \
zlib1g \
debconf \
net-tools \
file \
imagemagick \
mesa-utils \
tgt \
iptables \
psmisc \
man \
htop \
lsof \
strace
