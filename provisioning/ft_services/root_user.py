# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning._core import Fleet
from provisioning._core import Run
from provisioning.fleet import sc_ft

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    Fleet.compose([sc_ft]).run([
        # User lingering allows users who are not logged in to run long-running services (like systemd services).
        Run('sudo loginctl enable-linger root'),
        ])
