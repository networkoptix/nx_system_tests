# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning import Run
from provisioning.fleet import beg_ft002
from provisioning.ft_services.python_services import LaunchSimpleSystemdService

_dir = Path(__file__).parent

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    beg_ft002.run([
        # See: https://drive.google.com/drive/folders/1MVYP_9q0tSfN9XwEi0Fbl8LpttO6uE5a
        # qcow2target package should be placed to /root manually.
        Run('sudo dpkg -i /root/qcow2target_240415164320_amd64.deb'),
        Run('sudo systemctl stop qcow2target_server.service'),
        Run('sudo systemctl disable qcow2target_server.service'),
        Run('sudo rm /tmp/qcow2target.sock'),
        LaunchSimpleSystemdService('ft', _dir / 'qcow2target.service'),
        ])
