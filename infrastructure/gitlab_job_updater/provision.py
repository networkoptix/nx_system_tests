# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from infrastructure._provisioning import SimpleServiceConfiguration
from infrastructure._provisioning import provision
from provisioning.fleet import sc_ft003_master


def main():
    configuration = SimpleServiceConfiguration(
        sc_ft003_master,
        Path(__file__).with_name('gitlab_job_updater.service'),
        )
    provision(configuration)
    return 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(main())
