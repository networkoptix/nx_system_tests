# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import InstallCommon
from provisioning._config_files import CommentLine
from provisioning._core import Fleet
from provisioning._core import Run
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft002_cloud
from provisioning.fleet import sc_ft003_master


def main():
    fl = Fleet.compose([
        sc_ft003_master,
        sc_ft002_cloud,
        sc_ft,
        ])
    fl.run([
        # Snaps are dependency-free packages. They update automatically.
        # See: https://snapcraft.io/docs
        # See: https://snapcraft.io/docs/keeping-snaps-up-to-date
        # See: https://askubuntu.com/a/1263653/249627
        Run('sudo snap refresh --hold=forever'),

        # motd-news makes a call periodically to Canonical servers
        # to get updated news for support and informational purposes.
        # See: https://ubuntu.com/legal/motd
        Run("""sudo sed /etc/default/motd-news -e 's/^ENABLED=1/ENABLED=0/'"""),

        # Disable ads and news from ubuntu-advantage-tools.
        # ubuntu-advantage-tools is used to attach machines to existing
        # Ubuntu Pro support contracts and initialise support services
        # such as Livepatch, FIPS, ESM and common criteria EAL2.
        # See: https://wiki.ubuntu.com/UbuntuAdvantageToolsUpdates
        # See: https://bugs.launchpad.net/ubuntu/+source/ubuntu-advantage-tools/+bug/1950692/comments/16
        # See: https://askubuntu.com/a/1457810/249627
        # See: https://askubuntu.com/a/1441036/249627
        Run('sudo pro config set apt_news=False'),

        # TODO: Consider replacing netplan and cloud-init with systemd-networkd.
        # During boot, Netplan generates configuration files
        # to hand off control to NetworkManager or Systemd-networkd.
        # Cloud-init is provisioning method for cloud instance initialisation.

        # Disable unattended-upgrades.
        # It downloads and installs upgrades automatically and unattended.
        # It could break network connections, touch something being in use
        # or otherwise disturb the running processes.
        # See: https://manpages.ubuntu.com/manpages/xenial/man8/unattended-upgrade.8.html
        # See: https://askubuntu.com/a/1479580/249627
        Run("""sudo sed /etc/apt/apt.conf.d/20auto-upgrades -i.bak -e '/^APT::Periodic::Update-Package-Lists/ s/"0"/"1"/'"""),
        Run("""sudo sed /etc/apt/apt.conf.d/20auto-upgrades -i.bak -e '/^APT::Periodic::Unattended-Upgrade/ s/"0"/"1"/'"""),
        Run('sudo dpkg-reconfigure -f noninteractive unattended-upgrades'),

        # Quick SSH login
        CommentLine('/etc/pam.d/sshd', 'pam_motd.so'),
        CommentLine('/etc/pam.d/sshd', 'pam_mail.so'),
        CommentLine('/etc/pam.d/login', 'pam_motd.so'),
        CommentLine('/etc/pam.d/login', 'pam_mail.so'),

        # SSH config
        InstallCommon('ft', 'provisioning/common/sshd-20-client-alive.conf', '/etc/ssh/sshd_config.d/'),
        Run('sudo sshd -T'),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
