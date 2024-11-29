# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning import CompositeCommand
from provisioning import Run
from provisioning._core import InstallCommon
from provisioning.fleet import beg_ft002

_dir = Path(__file__).parent
_network_dir = _dir / 'dnsmasq.d'

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    beg_ft002.run([
        Run('sudo apt install -y dnsmasq'),
        InstallCommon('root', 'provisioning/arms/dnsmasq.conf', '/etc/'),
        CompositeCommand([
            InstallCommon('root', str(path), '/etc/dnsmasq.d/')
            for path in _network_dir.glob('*.conf')
            ]),
        Run('sudo systemctl restart dnsmasq.service'),
        ])
