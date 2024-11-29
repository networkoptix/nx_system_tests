# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import shlex
from pathlib import Path
from subprocess import CalledProcessError

from provisioning import CompositeCommand
from provisioning import Fleet
from provisioning.ft_services.python_services import FetchRepo
from provisioning.ft_services.python_services import LaunchSimpleSystemdService
from provisioning.ft_services.python_services import SystemCtl
from provisioning.ft_services.python_services import UploadSystemdFile

ROOT_DIR = 'comparison_tests_control_panel'


def main():
    try:
        Fleet(['sc-ft002.nxlocal']).run([
            _Disable('ft'),
            ])
    except CalledProcessError as ex:
        _logger.warning(ex.stderr)
        _logger.warning(ex.stdout)
    Fleet(['sc-ft002.nxlocal']).run([
        _Deploy('ft'),
        ])


class _Deploy(CompositeCommand):

    def __init__(
            self,
            ssh_user: str,
            ):
        root_path = f'/home/{shlex.quote(ssh_user)}/{ROOT_DIR}/ft'
        super().__init__([
            FetchRepo(ssh_user, root_path),
            UploadSystemdFile(ssh_user, Path(__file__).with_name('comparison_control_panel.service')),
            LaunchSimpleSystemdService(ssh_user, Path(__file__).with_name('comparison_control_panel.service')),
            SystemCtl(ssh_user, 'daemon-reload'),
            ])


class _Disable(CompositeCommand):

    def __init__(
            self,
            ssh_user: str,
            ):
        root_path = f'/home/{shlex.quote(ssh_user)}/{ROOT_DIR}/ft'
        super().__init__([
            FetchRepo(ssh_user, root_path),
            SystemCtl(ssh_user, 'stop', 'comparison_control_panel.service'),
            SystemCtl(ssh_user, 'disable', 'comparison_control_panel.service'),
            SystemCtl(ssh_user, 'daemon-reload'),
            ])


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    _logger = logging.getLogger(__name__)
    main()
