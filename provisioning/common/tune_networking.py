# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import InstallCommon
from provisioning._core import Fleet
from provisioning._core import Run
from provisioning.fleet import beg_ft001
from provisioning.fleet import beg_ft002
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft002_cloud
from provisioning.fleet import sc_ft003_master


def main():
    fl = Fleet.compose([
        sc_ft,
        sc_ft003_master,
        sc_ft002_cloud,
        beg_ft001,
        beg_ft002,
        ])
    fl.run([
        InstallCommon('root', 'provisioning/common/80-high-bdp.conf', '/etc/sysctl.d/'),
        Run('sudo sysctl --system'),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
