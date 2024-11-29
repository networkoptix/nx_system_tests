# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from provisioning._core import Run
from provisioning.fleet import sc_ft


def main():
    sc_ft.run([
        # To manipulate with ISO and floppy images, needed for base snapshots.
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install -y mtools genisoimage'),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
