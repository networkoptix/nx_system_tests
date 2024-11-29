# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import shlex
from pathlib import Path

from long_tests._provisioning import StopAndDisableSystemdService
from provisioning import CompositeCommand
from provisioning.fleet import Fleet
from provisioning.ft_services.python_services import FetchRepo
from provisioning.ft_services.python_services import LaunchSimpleSystemdService
from provisioning.ft_services.python_services import SystemCtl
from provisioning.ft_services.python_services import UploadSystemdFile


def main():
    Fleet(['sc-ft002.nxlocal']).run([
        _Disable('ft'),
        _Deploy('ft'),
        ])


class _Deploy(CompositeCommand):

    def __init__(
            self,
            ssh_user: str,
            ):
        super().__init__([
            FetchRepo(ssh_user, f'/home/{shlex.quote(ssh_user)}/comparison_tests/ft'),
            UploadSystemdFile(ssh_user, Path(__file__).with_name('comparison_tests@.service')),
            LaunchSimpleSystemdService(ssh_user, Path(__file__).with_name('comparison_tests_vms_6.0_patch.timer')),
            LaunchSimpleSystemdService(ssh_user, Path(__file__).with_name('comparison_tests_vms_6.0.1.timer')),
            LaunchSimpleSystemdService(ssh_user, Path(__file__).with_name('comparison_tests_master.timer')),
            SystemCtl(ssh_user, 'daemon-reload'),
            ])


class _Disable(CompositeCommand):

    def __init__(self, ssh_user: str):
        super().__init__([
            FetchRepo(ssh_user, f'/home/{shlex.quote(ssh_user)}/comparison_tests/ft'),
            StopAndDisableSystemdService(ssh_user, 'comparison_tests_vms_6.0_patch.timer'),
            StopAndDisableSystemdService(ssh_user, 'comparison_tests_vms_6.0.1.timer'),
            StopAndDisableSystemdService(ssh_user, 'comparison_tests_master.timer'),
            SystemCtl(ssh_user, 'daemon-reload'),
            ])


if __name__ == '__main__':
    main()
