# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning._core import Fleet
from provisioning._core import Run
from provisioning.fleet import sc_ft003_master

_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    fl = Fleet.compose([
        sc_ft003_master,
        ])
    fl.run([
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y nginx-core'),
        ])
