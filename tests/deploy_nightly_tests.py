# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning.fleet import sc_ft003_master
from provisioning.ft_services.python_services import FetchRepo
from provisioning.ft_services.python_services import LaunchSimpleSystemdService
from provisioning.ft_services.python_services import UploadSystemdFile


def main():
    sc_ft003_master.run([
        FetchRepo('ft', '~ft/ft_nightly/ft'),
        UploadSystemdFile('ft', Path(__file__).with_name('ft_nightly@.service')),
        LaunchSimpleSystemdService('ft', Path(__file__).with_name('ft_nightly_master.timer')),
        LaunchSimpleSystemdService('ft', Path(__file__).with_name('ft_nightly_vms_6.0.timer')),
        LaunchSimpleSystemdService('ft', Path(__file__).with_name('ft_nightly_vms_6.0.1.timer')),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
