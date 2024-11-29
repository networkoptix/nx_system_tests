# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning import Run
from provisioning.fleet import beg_ft002
from provisioning.ft_services.python_services import FetchRepo
from provisioning.ft_services.python_services import LaunchSimpleSystemdService

_dir = Path(__file__).parent

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    # TFTP module must be run on UDP port 69 which is the privileged one
    # See: https://www.w3.org/Daemon/User/Installation/PrivilegedPorts.html
    beg_ft002.run([
        Run('sudo apt install -y authbind'),
        Run('sudo touch /etc/authbind/byport/69'),
        Run('sudo chown root:ft /etc/authbind/byport/69'),
        Run('sudo chmod 650 /etc/authbind/byport/69'),
        FetchRepo('ft', '~ft/ptftp/ft'),
        LaunchSimpleSystemdService('ft', _dir / 'ptftp.service'),
        ])
