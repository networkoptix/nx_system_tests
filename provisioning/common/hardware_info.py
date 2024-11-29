# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning._core import Command
from provisioning._core import Fleet
from provisioning._ssh import ssh


class HardwareInfo(Command):

    def __repr__(self):
        return f'{HardwareInfo.__name__}()'

    def run(self, host):
        ssh(host, 'sudo apt install -y lshw')
        process = ssh(host, 'sudo lshw -class system -class processor -class memory && lsblk -o model,size,name -d')
        path = Path(__file__).with_name('hardware').joinpath(host + '.txt')
        path.parent.mkdir(exist_ok=True)
        path.write_bytes(process.stdout)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    fl = Fleet([
        'sc-ft001.nxlocal',
        'sc-ft002.nxlocal',
        'sc-ft003.nxlocal',
        'sc-ft004.nxlocal',
        'sc-ft005.nxlocal',
        'sc-ft006.nxlocal',
        'sc-ft007.nxlocal',
        'sc-ft008.nxlocal',
        'sc-ft009.nxlocal',
        'sc-ft010.nxlocal',
        'sc-ft011.nxlocal',
        'sc-ft012.nxlocal',
        'sc-ft013.nxlocal',
        'sc-ft014.nxlocal',
        'sc-ft015.nxlocal',
        'sc-ft016.nxlocal',
        'sc-ft017.nxlocal',
        'sc-ft018.nxlocal',
        'sc-ft019.nxlocal',
        'sc-ft020.nxlocal',
        'sc-ft021.nxlocal',
        'sc-ft022.nxlocal',
        'sc-ft023.nxlocal',
        'sc-ft024.nxlocal',
        ])
    fl.run([
        HardwareInfo(),
        ])
