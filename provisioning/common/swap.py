# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning._core import Fleet
from provisioning._core import Run
from provisioning.fleet import beg_ft002
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft002_cloud
from provisioning.fleet import sc_ft003_master

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    fl = Fleet.compose([
        beg_ft002,
        sc_ft003_master,
        sc_ft002_cloud,
        sc_ft,
        ])
    fl.run([
        Run('sudo sysctl vm.swappiness=5'),
        # See files with: sudo swapon --show=NAME --noheadings --raw
        Run('sudo swapoff --all'),
        # Allocate space without holes. On modern filesystems, preallocation is
        # done quickly by allocating blocks and marking them as uninitialized,
        # requiring no IO to the data blocks. This is much faster than creating
        # a file by filling it with zeroes.
        # See: https://manpages.ubuntu.com/manpages/jammy/en/man1/fallocate.1.html
        # See: https://unix.stackexchange.com/a/697424/152472
        Run('sudo fallocate -x -l 16G /swap.img'),
        Run('sudo chmod u=rw,g=,o= /swap.img'),
        Run('sudo mkswap /swap.img'),
        Run('sudo swapon /swap.img'),
        Run(r'sudo sed -i "/\/swap.img/s/^ *#\+ *//g" /etc/fstab'),
        ])
