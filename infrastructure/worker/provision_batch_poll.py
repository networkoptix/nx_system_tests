# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from infrastructure._provisioning import MultiProcessServiceConfiguration
from infrastructure._provisioning import provision
from provisioning.fleet import sc_ft003_master


def main():
    configuration = MultiProcessServiceConfiguration(
        sc_ft003_master,
        Path(__file__).with_name('worker_batch_poll.target'),
        Path(__file__).with_name('worker_batch_poll@.service'),
        )
    provision(configuration)
    return 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(main())