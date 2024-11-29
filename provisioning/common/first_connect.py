# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning._core import Fleet
from provisioning._known_hosts import FirstConnect
from provisioning.common.hardware_info import HardwareInfo
from provisioning.fleet import beg_ft002
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft002_cloud
from provisioning.fleet import sc_ft003_master

_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    fl = Fleet.compose([
        sc_ft003_master,
        sc_ft002_cloud,
        sc_ft,
        beg_ft002,
        ])
    fl.run([
        FirstConnect(),
        HardwareInfo(),
        ])
