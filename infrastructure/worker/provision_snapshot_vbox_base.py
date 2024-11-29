# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from infrastructure._provisioning import MultiProcessServiceConfiguration
from infrastructure._provisioning import provision
from provisioning import Fleet


def main():
    fleet = Fleet([
        'sc-ft022.nxlocal',
        'sc-ft023.nxlocal',
        'sc-ft024.nxlocal',
        ])
    configuration = MultiProcessServiceConfiguration(
        fleet,
        Path(__file__).with_name('worker_snapshot_vbox_base.target'),
        Path(__file__).with_name('worker_snapshot_vbox_base@.service'),
        )
    provision(configuration)
    return 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(main())
