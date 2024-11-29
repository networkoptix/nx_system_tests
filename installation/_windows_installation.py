# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from abc import ABCMeta
from typing import Collection
from typing import Mapping
from typing import Optional
from typing import Tuple
from uuid import UUID

from distrib import Customization
from distrib import Version
from installation._base_installation import BaseInstallation
from os_access import RemotePath
from os_access import WindowsAccess
from os_access._windows_registry import ValueNotFoundError

_logger = logging.getLogger(__name__)


def _find_installations(
        windows_access: WindowsAccess,
        known_display_names: Collection[str]) -> Collection[Tuple[str, Optional[Version], str]]:
    # The function looks for records made by 32-bit installers.
    # 64-bit installers make records in
    # "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall" subtree
    # and put the uninstall command in the "UninstallString" key.
    # TODO: Implement a generic function.
    result = []
    subtree = r'HKLM\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall'
    program_keys = windows_access.registry.list_keys(subtree)
    for program_key_name in program_keys:
        try:
            # The Nx programs can be located in UUID-named folders
            UUID(program_key_name)
        except ValueError:
            _logger.debug("The %r is not UUID", program_key_name)
            continue
        program_key = subtree + '\\' + program_key_name
        try:
            name = windows_access.registry.get_string(program_key, 'DisplayName')
        except ValueNotFoundError:
            _logger.debug("No DisplayName, incomplete installation, skip: %s", program_key)
            continue
        if name not in known_display_names:
            _logger.debug("The %r is not NX product", program_key)
            continue
        try:
            installed_version = Version(
                windows_access.registry.get_string(program_key, 'DisplayVersion'))
        except ValueNotFoundError:
            _logger.warning(
                "No DisplayVersion, incomplete installation, try to uninstall anyway: %s",
                program_key)
            installed_version = None
        try:
            uninstall_str = windows_access.registry.get_string(program_key, 'QuietUninstallString')
        except ValueNotFoundError:
            _logger.warning(
                "No QuietUninstallString, incomplete installation, skip: %s", program_key)
            continue
        result.append((name, installed_version, uninstall_str))
    return result


class WindowsInstallation(BaseInstallation, metaclass=ABCMeta):
    os_access: WindowsAccess  # Defined in child class
    _customization_by_display_name: Mapping[str, Customization]  # Defined in child class

    def uninstall_all(self):
        installations = self._find_registry_entries(self.os_access)
        for [_, _, uninstall_command] in installations:
            self.os_access.run(uninstall_command, timeout_sec=120)

    @classmethod
    def _find_registry_entries(
            cls,
            os_access: WindowsAccess,
            ) -> Collection[Tuple[Customization, Optional[Version], str]]:
        known_display_names = [k for k in cls._customization_by_display_name]
        installations = _find_installations(os_access, known_display_names)
        return [
            (
                cls._customization_by_display_name[display_name],
                version,
                uninstall_str,
                )
            for [display_name, version, uninstall_str] in installations
            ]

    def _run_installer_command(self, installer: RemotePath):
        commands = {
            # The wildcard (*) means that all logs except verbose (v) and extra (x) logs
            # will be collected. For more details, please see:
            # https://docs.microsoft.com/en-us/windows/win32/msi/command-line-options
            '.msi': ['MsiExec', '/i', installer, '/passive', '/l*v'],
            '.exe': [installer, '/passive', '/l*v'],
            }
        self.os_access.run(
            commands[installer.suffix], timeout_sec=300)
