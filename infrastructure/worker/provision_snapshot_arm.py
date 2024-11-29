# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from pathlib import Path
from pathlib import PurePosixPath

from infrastructure._provisioning import ProvisionConfiguration
from infrastructure._provisioning import provision
from provisioning import CompositeCommand
from provisioning import Fleet
from provisioning import Run
from provisioning.ft_services.python_services import FetchRepo
from provisioning.ft_services.python_services import LaunchSimpleSystemdService
from provisioning.ft_services.python_services import PrepareVenv
from provisioning.ft_services.python_services import SystemCtl
from provisioning.ft_services.python_services import UploadSystemdFile


def main():
    target_file = Path(__file__).with_name('worker_snapshot_arm.target')
    repo_dir = PurePosixPath(f'~ft/{target_file.name}/ft')
    jetsonnano_file = Path(__file__).with_name('worker_snapshot_jetsonnano@.service')
    rpi4_file = Path(__file__).with_name('worker_snapshot_rpi4@.service')
    rpi5_file = Path(__file__).with_name('worker_snapshot_rpi5@.service')
    orinnano_file = Path(__file__).with_name('worker_snapshot_orinnano@.service')
    configuration = ProvisionConfiguration(
        target_file.name,
        Fleet(['beg-ft002.nxlocal']),
        deploy=CompositeCommand([
            FetchRepo('ft', str(repo_dir)),
            PrepareVenv('ft', f'~ft/{target_file.name}/ft', 'infrastructure'),
            UploadSystemdFile('ft', jetsonnano_file),
            UploadSystemdFile('ft', rpi4_file),
            UploadSystemdFile('ft', rpi5_file),
            UploadSystemdFile('ft', orinnano_file),
            SystemCtl('ft', 'daemon-reload'),
            LaunchSimpleSystemdService('ft', target_file),
            ]),
        cleanup=CompositeCommand([
            SystemCtl('ft', 'stop', target_file.name),
            SystemCtl('ft', 'disable', target_file.name),
            Run(f'sudo -u ft rm -rf {repo_dir.parent}'),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{target_file.name}'),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{jetsonnano_file.name}'),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{rpi4_file.name}'),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{rpi5_file.name}'),
            Run(f'sudo -u ft rm -f ~ft/.config/systemd/user/{orinnano_file.name}'),
            ]),
        start_after_failure=SystemCtl('ft', 'start', target_file.name),
        )
    provision(configuration)
    return 0


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    exit(main())
