# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import InstallCommon
from provisioning import Run
from provisioning.fleet import beg_ft002

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    beg_ft002.run([
        InstallCommon('root', 'provisioning/arms/network/8021q.conf', '/etc/modules-load.d/'),
        InstallCommon('root', 'provisioning/arms/network/50_eno4', '/etc/network/interfaces.d/'),
        InstallCommon('root', 'provisioning/arms/network/60_eno4.3', '/etc/network/interfaces.d/'),
        InstallCommon('root', 'provisioning/arms/network/60_eno4.4', '/etc/network/interfaces.d/'),
        InstallCommon('root', 'provisioning/arms/network/60_eno4.5', '/etc/network/interfaces.d/'),
        Run('sudo ifdown eno4.5'),
        Run('sudo ifdown eno4.4'),
        Run('sudo ifdown eno4.3'),
        Run('sudo ifdown eno4'),
        Run('sudo ifup -a'),
        InstallCommon('root', 'provisioning/arms/50-ip-forward.conf', '/etc/sysctl.d/'),
        Run('sudo sysctl --system'),
        Run('sudo DEBIAN_FRONTEND=noninteractive apt install -y iptables iptables-persistent'),
        InstallCommon('root', 'provisioning/arms/rules.v4', '/etc/iptables/'),
        Run('sudo systemctl restart iptables.service'),
        ])
