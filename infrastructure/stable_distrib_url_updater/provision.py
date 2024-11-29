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
from provisioning.ft_services.python_services import PrepareVenv
from provisioning.ft_services.python_services import SystemCtl
from provisioning.ft_services.python_services import UploadSystemdFile


def main():
    repo_dir = PurePosixPath('~ft/stable_distrib_url_updater/ft')
    service = Path(__file__).with_name('stable_distrib_url_updater@.service')
    vms_master_timer = Path(__file__).with_name('stable_distrib_url_updater_master.timer')
    vms_5_1_patch_timer = Path(__file__).with_name('stable_distrib_url_updater_vms_5.1_patch.timer')
    vms_6_0_timer = Path(__file__).with_name('stable_distrib_url_updater_vms_6.0.timer')
    vms_6_0_patch_timer = Path(__file__).with_name('stable_distrib_url_updater_vms_6.0_patch.timer')
    vms_6_0_1_timer = Path(__file__).with_name('stable_distrib_url_updater_vms_6.0.1.timer')
    configuration = ProvisionConfiguration(
        service.name,
        sc_ft003_master,
        deploy=CompositeCommand([
            FetchRepo('ft', str(repo_dir)),
            PrepareVenv('ft', '~ft/stable_distrib_url_updater/ft', 'infrastructure'),
            UploadSystemdFile('ft', service),
            LaunchSimpleSystemdService('ft', vms_master_timer),
            LaunchSimpleSystemdService('ft', vms_5_1_patch_timer),
            LaunchSimpleSystemdService('ft', vms_6_0_timer),
            LaunchSimpleSystemdService('ft', vms_6_0_patch_timer),
            LaunchSimpleSystemdService('ft', vms_6_0_1_timer),
            ]),
        cleanup=CompositeCommand([
            SystemCtl('ft', 'stop', vms_master_timer.name),
            SystemCtl('ft', 'disable', vms_master_timer.name),
            SystemCtl('ft', 'stop', vms_5_1_patch_timer.name),
            SystemCtl('ft', 'disable', vms_5_1_patch_timer.name),
            SystemCtl('ft', 'stop', vms_6_0_timer.name),
            SystemCtl('ft', 'disable', vms_6_0_timer.name),
            SystemCtl('ft', 'stop', vms_6_0_patch_timer.name),
            SystemCtl('ft', 'disable', vms_6_0_patch_timer.name),
            SystemCtl('ft', 'stop', vms_6_0_1_timer.name),
            SystemCtl('ft', 'disable', vms_6_0_1_timer.name),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{vms_master_timer.name}'),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{vms_5_1_patch_timer.name}'),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{vms_6_0_timer.name}'),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{vms_6_0_patch_timer.name}'),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{vms_6_0_1_timer.name}'),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{service.name}'),
            Run(f'sudo -u ft rm -rf {repo_dir.parent}'),
            ]),
        start_after_failure=CompositeCommand([
            SystemCtl('ft', 'start', vms_master_timer.name),
            SystemCtl('ft', 'start', vms_5_1_patch_timer.name),
            SystemCtl('ft', 'start', vms_6_0_timer.name),
            SystemCtl('ft', 'start', vms_6_0_patch_timer.name),
            SystemCtl('ft', 'start', vms_6_0_1_timer.name),
            ]),
        )
    provision(configuration)
    return 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(main())
