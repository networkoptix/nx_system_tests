# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import shlex
from pathlib import Path

from config import global_config
from infrastructure._provisioning import ProvisionConfiguration
from infrastructure._provisioning import provision
from provisioning import CompositeCommand
from provisioning import Run
from provisioning.fleet import sc_ft003_master
from provisioning.ft_services.python_services import LaunchSimpleSystemdService
from provisioning.ft_services.python_services import SystemCtl


def main():
    repo_uri = shlex.quote(global_config['ft_fetch_origin_uri'])
    service_file = Path(__file__).with_name('git_mirror.service')
    configuration = ProvisionConfiguration(
        service_file.name,
        sc_ft003_master,
        deploy=CompositeCommand([
            Run('sudo -Hu ft mkdir -p ~ft/git_mirror/ft.git'),
            Run('sudo -Hu ft git -C ~ft/git_mirror/ft.git init --bare -q'),
            Run('sudo -Hu ft git -C ~ft/git_mirror/ft.git remote remove origin'),
            Run(f'sudo -Hu ft git -C ~ft/git_mirror/ft.git remote add --mirror=fetch origin {repo_uri}'),
            Run('sudo -Hu ft git -C ~ft/git_mirror/ft.git remote update'),
            Run('sudo -Hu ft touch ~ft/git_mirror/ft.git/git-daemon-export-ok'),
            LaunchSimpleSystemdService('ft', service_file),
            ]),
        cleanup=CompositeCommand([
            SystemCtl('ft', 'stop', service_file.name),
            SystemCtl('ft', 'disable', service_file.name),
            Run('sudo -u ft rm -rf ~ft/git_mirror'),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{service_file.name}'),
            ]),
        start_after_failure=SystemCtl('ft', 'start', service_file.name),
        )
    provision(configuration)
    return 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(main())
