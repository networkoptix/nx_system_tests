# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from abc import ABCMeta
from subprocess import CalledProcessError
from typing import Mapping

from distrib import Customization
from installation._base_installation import BaseInstallation
from installation._base_installation import CannotInstall
from installation._mediaserver import AnotherCloud
from os_access import PosixAccess
from os_access import RemotePath

_logger = logging.getLogger(__name__)


class DpkgInstallation(BaseInstallation, metaclass=ABCMeta):
    os_access: PosixAccess  # Defined in child class
    _known_packages: Mapping[str, Customization]  # Defined in child class
    _component_name: str  # Defined in child class

    @property
    def _posix_shell(self):
        return self.os_access.shell

    def uninstall_all(self):
        outcome = self._posix_shell.run([
            'dpkg-query',
            '--show',
            '--showformat', '${Package}\n',
            ])
        installed_packages = outcome.stdout.decode('ascii').splitlines()
        installed_product_packages = []
        for package_name in installed_packages:
            if self._component_name not in package_name:
                continue
            for known_package_name in self._known_packages:
                if package_name.startswith(known_package_name):
                    installed_product_packages.append(known_package_name)
                    break
        _logger.debug("Installed products: %s", installed_product_packages)
        if not installed_product_packages:
            return
        # There was a period when mediaservers with different cloud hosts
        # have cloud host suffix. That's why arg ends with a wildcard.
        args = [name + '*' for name in installed_product_packages]
        self._posix_shell.run(
            ['apt-get', 'purge', '--yes', *args],
            env={'DEBIAN_FRONTEND': 'noninteractive'},  # Suppress dialogs.
            timeout_sec=300,  # Service may hang when stopping.
            )

    def _wait_on_dpkg_lock(self, timeout_sec=180):
        started_at = time.monotonic()
        while True:
            try:
                self._posix_shell.run(['lsof', '-t', '/var/lib/dpkg/lock'])
            except CalledProcessError as e:
                if e.returncode == 1 and not e.stderr:
                    return
                raise e
            if time.monotonic() > started_at + timeout_sec:
                raise RuntimeError("Timeout waiting for dpkg lock to release.")
            _logger.info("Waiting for dpkg lock to release.")
            time.sleep(3)

    def run_installer(self, installer: RemotePath):
        self._wait_on_dpkg_lock()
        try:
            self._posix_shell.run(
                args=['dpkg', '--install', installer],
                env={'DEBIAN_FRONTEND': 'noninteractive'},
                timeout_sec=300,  # The existing mediaserver service may hang when stopping.
                )
        except CalledProcessError as e:
            if e.returncode == 1:
                if b'package is for another instance of Nx Cloud' in e.stderr:
                    raise AnotherCloud()
            if b'is locked by another process' in e.stderr:
                output = self._posix_shell.run(['lsof', '-t', '/var/lib/dpkg/lock']).stdout
                [pid, *_] = output.decode().split()
                tree = self._posix_shell.run(['pstree', '-sapA', pid]).stdout.decode()
                raise RuntimeError("Dpkg is locked by:\n{}".format(tree))
            raise CannotInstall(str(e))
