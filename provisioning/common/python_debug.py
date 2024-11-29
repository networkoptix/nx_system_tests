# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning import Fleet
from provisioning import Run
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft003_master


def main():
    """Install GDB for taking backtrace.

    Attach:

        sudo gdb -p 2103757

    Take Python backtrace:

        set pagination off
        set logging on
        source /usr/share/gdb/auto-load/usr/bin/python3.10-gdb.py
        thread apply all py-bt-full
        detach
        quit
    """
    fl = Fleet.compose([
        sc_ft003_master,
        sc_ft,
        ])
    fl.run([
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y gdb python3-dbg'),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
