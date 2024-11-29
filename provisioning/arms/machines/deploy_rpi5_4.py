# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning import Run
from provisioning.fleet import beg_ft002
from provisioning.ft_services.python_services import FetchRepo
from provisioning.ft_services.python_services import LaunchSimpleSystemdService
from provisioning.ft_services.python_services import PrepareVenv

_dir = Path(__file__).parent
_repo_dir = '~ft/machines/rpi5_4'

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    beg_ft002.run([
        Run('sudo apt install -y git ssh-askpass python3-venv'),
        FetchRepo('ft', _repo_dir),
        PrepareVenv('ft', _repo_dir, 'arms'),
        LaunchSimpleSystemdService('ft', _dir / 'rpi5-4.service'),
        ])
