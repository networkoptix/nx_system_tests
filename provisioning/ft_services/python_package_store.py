# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import shlex
from pathlib import Path
from typing import Collection

from provisioning import InstallCommon
from provisioning._core import Command
from provisioning._core import Fleet
from provisioning._core import Run
from provisioning._ssh import ssh
from provisioning.fleet import sc_ft
from provisioning.fleet import sc_ft003_master


class MakePythonPackageStore(Command):
    """Pin Python package versions, allow for installation without Internet.

    Once a new package was added, and 200 workers rushed to download it
    from PyPI. PyPI rejected most of the requests. The tests failed.
    PyPI may have recorded the incident. Hence the Python package store.

    Later, Internet was blocked on CI. If PyPI had still been used, its CDN
    addresses would've had to be allowed in firewall (iptables).

    New packages should be added to the store before they are used on CI.
    Not to forget that, it's recommended for developers to use the same store.

    One Python package store should be configured per network location.
    """

    def __init__(self, pip_command, requirements: Collection[str]):
        self._requirements = requirements
        self._pip_command = pip_command

    def __repr__(self):
        return f'{MakePythonPackageStore.__name__}({self._pip_command!r}, {self._requirements!r})'

    def run(self, host):
        path = '/home/ft/.cache/pip-download/'
        self._run_as_user(host, ['mkdir', '-p', path])
        self._run_as_user(host, [
            *self._pip_command,
            'download', '-d', path,
            *self._requirements,
            ])

    @staticmethod
    def _run_as_user(host, command):
        ssh(host, 'sudo -Hu ft ' + shlex.join(command))


def read_requirements_txt(repo_path):
    repo_path = Path(repo_path)
    assert not repo_path.is_absolute()
    path = Path(__file__).parent.parent.parent / repo_path
    return path.read_text().splitlines()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    all_machines = Fleet.compose([
        sc_ft003_master,
        sc_ft,
        ])
    all_machines.run([
        Run('sudo DEBIAN_FRONTEND=noninteractive apt-get install python3-venv'),
        Run('sudo -u ft python3 -m venv ~ft/.config/pip-venv'),
        InstallCommon('ft', 'provisioning/ft_services/pip.conf', '~ft/.config/pip/'),
        ])
    pip_command = ['/home/ft/.config/pip-venv/bin/python3', '-m', 'pip', '--isolated']
    masters = Fleet.compose([
        sc_ft003_master,
        ])
    requirements = [
        *read_requirements_txt('requirements.txt'),
        *read_requirements_txt('infrastructure/ft_view/requirements.txt'),
        *read_requirements_txt('linter/requirements.txt'),
        *read_requirements_txt('infrastructure/requirements.txt'),
        *read_requirements_txt('arms/requirements.txt'),
        ]
    masters.run([
        MakePythonPackageStore(pip_command, [
            *requirements,
            '--no-deps',
            ]),
        MakePythonPackageStore(pip_command, [
            *requirements,
            '--python-version=3.11',
            '--no-deps',
            ]),
        MakePythonPackageStore(pip_command, [
            *requirements,
            '--python-version=3.12',
            '--no-deps',
            ]),
        MakePythonPackageStore(pip_command, [
            *requirements,
            'colorama',  # Windows-only Flask requirement
            'pyreadline3',  # Windows-only Flask requirement
            '--platform=win_amd64',
            '--python-version=3.10',
            '--no-deps',
            ]),
        MakePythonPackageStore(pip_command, [
            *requirements,
            'colorama',  # Windows-only Flask requirement
            'pyreadline3',  # Windows-only Flask requirement
            '--platform=win_amd64',
            '--python-version=3.11',
            '--no-deps',
            ]),
        MakePythonPackageStore(pip_command, [
            *requirements,
            'colorama',  # Windows-only Flask requirement
            'pyreadline3',  # Windows-only Flask requirement
            '--platform=win_amd64',
            '--python-version=3.12',
            '--no-deps',
            ]),
        MakePythonPackageStore(pip_command, [
            # Packages required for NX AI Manager tests.
            'certifi==2024.8.30',
            'charset-normalizer==3.4.0',
            'distinctipy==1.3.4',
            'GPUtil==1.4.0',
            'idna==3.10',
            'msgpack==1.1.0',
            'numpy==2.1.3',
            'opencv-python==4.10.0.84',
            'pillow==11.0.0',
            'psutil==6.1.0',
            'py-cpuinfo==9.0.0',
            'requests==2.32.3',
            'sysv-ipc==1.1.0',
            'urllib3==2.2.3',
            '--platform=manylinux_2_17_aarch64',
            '--python-version=3.11',
            '--no-deps',
            ]),
        InstallCommon('ft', 'provisioning/ft_services/pip.us.nginx.conf', '/etc/nginx/sites-available/'),
        Run('sudo ln -s -f /etc/nginx/sites-available/pip.us.nginx.conf /etc/nginx/sites-enabled/pip'),
        Run('sudo systemctl reload nginx'),
        ])
_logger = logging.getLogger(__name__)
