# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path

from provisioning.fleet import beg_ft001
from provisioning.ft_services.python_services import FetchRepo
from provisioning.ft_services.python_services import LaunchSimpleSystemdService
from provisioning.ft_services.python_services import UploadSystemdFile


def main():
    beg_ft001.run([
        FetchRepo('ft', '~ft/rct_nightly/ft'),
        UploadSystemdFile('ft', Path(__file__).with_name('rct_nightly@.service')),
        LaunchSimpleSystemdService(
            'ft', Path(__file__).with_name('rct_nightly_master.timer')),
        LaunchSimpleSystemdService(
            'ft', Path(__file__).with_name('rct_nightly_vms_6.0.timer')),
        LaunchSimpleSystemdService(
            'ft', Path(__file__).with_name('rct_nightly_vms_5.1_patch.timer')),
        ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
