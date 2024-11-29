# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning.fleet import sc_ft003_master
from provisioning.ft_services.python_services import FetchRepo
from provisioning.ft_services.python_services import LaunchSimpleSystemdService
from provisioning.ft_services.python_services import PrepareVenv


def main():
    sc_ft003_master.run([
        FetchRepo('ft', '~ft/batches_api/ft'),
        PrepareVenv('ft', '~ft/batches_api/ft', 'infrastructure/ft_view'),
        LaunchSimpleSystemdService('ft', Path(__file__, '../batches_api.service').resolve()),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
