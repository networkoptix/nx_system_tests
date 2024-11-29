# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path
from pathlib import PurePosixPath

from infrastructure._provisioning import ProvisionConfiguration
from infrastructure._provisioning import provision
from provisioning import CompositeCommand
from provisioning import Run
from provisioning.fleet import sc_ft003_master
from provisioning.ft_services.python_services import FetchRepo
from provisioning.ft_services.python_services import LaunchSimpleSystemdService
from provisioning.ft_services.python_services import SystemCtl
from provisioning.ft_services.python_services import UploadSystemdFile


def main():
    crawler_service = Path(__file__).with_name('testrail_crawler.service')
    crawler_timer = Path(__file__).with_name('testrail_crawler.timer')
    web_service = Path(__file__).with_name('testrail_web.service')
    repo_dir = PurePosixPath('~ft/testrail_service/ft')
    configuration = ProvisionConfiguration(
        'Testrail service',
        sc_ft003_master,
        deploy=CompositeCommand([
            FetchRepo('ft', str(repo_dir)),
            UploadSystemdFile('ft', crawler_service),
            LaunchSimpleSystemdService('ft', crawler_timer),
            LaunchSimpleSystemdService('ft', web_service),
            ]),
        cleanup=CompositeCommand([
            SystemCtl('ft', 'stop', web_service.name),
            SystemCtl('ft', 'disable', web_service.name),
            SystemCtl('ft', 'stop', crawler_timer.name),
            SystemCtl('ft', 'disable', crawler_timer.name),
            Run(f'sudo -u ft rm -rf {repo_dir.parent}'),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{web_service.name}'),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{crawler_timer.name}'),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{crawler_service.name}'),
            ]),
        start_after_failure=SystemCtl('ft', 'restart', web_service.name),
        )
    provision(configuration)
    return 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(main())
