# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from provisioning import AddPubKey
from provisioning import AddUser
from provisioning import InstallCommon
from provisioning import RepoPubKey
from provisioning._config_files import CommentLine
from provisioning._core import Run
from provisioning._known_hosts import FirstConnect
from provisioning._users import AddUserToGroup
from provisioning.common.hardware_info import HardwareInfo
from provisioning.fleet import beg_ft001
from provisioning.ft_runs._virtual_box import InstallVirtualBox


def main():
    beg_ft001.run([
        FirstConnect(),
        # CUT: Personal accounts configuration
        # Quick SSH login
        CommentLine('/etc/pam.d/sshd', 'pam_motd.so'),
        CommentLine('/etc/pam.d/sshd', 'pam_mail.so'),
        CommentLine('/etc/pam.d/login', 'pam_motd.so'),
        CommentLine('/etc/pam.d/login', 'pam_mail.so'),
        ])
    beg_ft001.run([
        # Configure network
        InstallCommon('root', 'provisioning/ft_runs/belgrade/00-installer-config.yaml', '/etc/netplan/'),
        Run('sudo netplan apply'),
        # Configure NTP (used by Aruba switch)
        Run('sudo apt-get install -y openntpd'),
        InstallCommon('root', 'provisioning/ft_runs/belgrade/ntpd.conf', '/etc/openntpd/'),
        Run('sudo systemctl reload openntpd.service'),
        ])
    beg_ft001.run([
        HardwareInfo(),
        AddUser('ft'),
        Run('sudo -u ft chmod a+rX ~ft'),
        Run('sudo loginctl enable-linger ft'),
        InstallVirtualBox(),
        AddUserToGroup('ft', 'vboxusers'),
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv'),
        # VLC libraries with required plugins.
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y libvlc-bin vlc-plugin-base'),
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg'),
        # Install HTTP-share via provisioning/ft_services/ft_http_share.py
        ])


if __name__ == '__main__':
    main()
