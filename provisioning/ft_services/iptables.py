# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning import InstallCommon
from provisioning._core import Run
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft003_master
from provisioning.ft_services.python_services import LaunchSimpleSystemdService
from provisioning.ft_services.python_services import UploadSystemdFile


def main():
    """Restrict Internet access.

    Caveats with specifying DNS in iptables:
    1. If DNS records change, iptables rules are not updated.
    E.g. imap.gmail.com resolution change often (balancing, perhaps).
    That's why rules on port numbers were introduced.
    2. DNS server may be hijacked. But the goal is tests stability. If
    it causes any security flaws, the approach will be reconsidered.
    """
    sc_ft003_master.run([
        Run('sudo iptables -F OUTPUT'),
        ])
    sc_ft.run([
        InstallCommon('root', 'provisioning/ft_services/iptables_v4', '~root/'),
        UploadSystemdFile('root', Path(__file__).with_name('iptables_v4.service')),
        LaunchSimpleSystemdService('root', Path(__file__).with_name('iptables_v4.timer')),
        InstallCommon('root', 'provisioning/ft_services/iptables_v6', '~root/'),
        UploadSystemdFile('root', Path(__file__).with_name('iptables_v6.service')),
        LaunchSimpleSystemdService('root', Path(__file__).with_name('iptables_v6.timer')),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
