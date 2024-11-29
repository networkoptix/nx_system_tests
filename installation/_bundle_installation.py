# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import functools
import logging
import subprocess
import time
from subprocess import CalledProcessError

from distrib import Customization
from distrib import Version
from distrib import known_customizations
from installation._base_installation import CannotInstall
from installation._base_installation import OsNotSupported
from installation._mediaserver import AnotherCloud
from installation._windows_installation import WindowsInstallation
from os_access import CannotDelete
from os_access import RemotePath
from os_access import WindowsAccess

_logger = logging.getLogger(__name__)


class WindowsBundleInstallation(WindowsInstallation):

    _customization_by_display_name = {
        c.windows_bundle_display_name: c
        for c in known_customizations.values()
        if c.windows_bundle_display_name is not None}

    def __init__(self, os_access: WindowsAccess, customization: Customization, version: Version):
        if not isinstance(os_access, WindowsAccess):
            raise OsNotSupported(self.__class__, os_access)
        self._program_files_dir = os_access.program_files_dir()  # type: RemotePath
        self.installation_dir = self._program_files_dir / customization.windows_server_installation_subdir  # type: RemotePath
        super().__init__(os_access, self.installation_dir)
        self._build_info_file = self.dir / 'build_info.txt'  # type: RemotePath
        self._client_dir = self._program_files_dir / customization.windows_client_installation_subdir / str(version)  # type: RemotePath
        self._system_local_app_data = os_access.system_profile_dir() / 'AppData' / 'Local'  # type: RemotePath
        self._var = self._client_dir / self._system_local_app_data / customization.windows_server_app_data_subdir  # type: RemotePath
        self._installer_logs_dir = os_access.home() / 'AppData' / 'Local' / 'Temp'  # type: RemotePath
        self._executable = self._client_dir / (customization.windows_client_executable + '.exe')  # type: RemotePath
        self._config_key = customization.windows_server_registry_key

    def __repr__(self):
        return f'<{self.__class__.__name__} on {self.os_access!r}>'

    @property
    @functools.lru_cache()
    def _mediaserver_service(self):
        service_name = self._customization().windows_server_service_name
        return self.os_access.service(service_name)

    def clean_installer_local_user_logs(self):
        temp_dir = self.os_access.home() / 'AppData' / 'Local' / 'Temp'
        for file in temp_dir.glob("*Nx_Witness_*.log"):
            file.unlink(missing_ok=True)

    @staticmethod
    def _delete_tray_assistant_link(link):
        # Link file can be locked by some process, which rarely leads to error on unlink() call.
        # Retry file deletion on such error.
        attempts = 5
        for attempt in range(1, attempts + 1):
            _logger.info(
                "Attempt %d to remove Tray Assistant link %s from Start Menu Startup.",
                attempt, link)
            try:
                link.unlink()
            except CannotDelete as e:
                [_error_code, message] = e.args
                _logger.info("Failed to delete %s: %s", link, message)
                time.sleep(0.5)
            else:
                return
        raise RuntimeError(
            f"Failed to delete tray assistant link {link}: file is locked by some process")

    # It locked nx_network.dll, which is patched when changing cloud host
    # name, cramping mediaserver setup and cleanup.
    def discard_tray_assistant(self):
        program_data = self.os_access.program_data_dir()
        startup = program_data / 'Microsoft' / 'Windows' / 'Start Menu' / 'Programs' / 'Startup'
        for link in startup.glob('* Tray Assistant.lnk'):
            self._delete_tray_assistant_link(link)
        try:
            # TODO: Rewrite with Process class and WMI.
            _logger.debug("Stop Tray Assistant.")
            self.os_access.run(['TaskKill', '/F', '/IM', 'traytool.exe'])
        except subprocess.CalledProcessError:
            _logger.debug("Tray Assistant is not running.")
        else:
            _logger.info("Successfully stopped Tray Assistant.")

    def _wait_for_server_service_started(self):
        started_at = time.monotonic()
        timeout_sec = 10
        _logger.debug("Waiting for server to start for %d seconds", timeout_sec)
        while True:
            if self._mediaserver_service.is_running():
                return
            elapsed_time = time.monotonic() - started_at
            _logger.debug(
                "%s is not started after %.2f seconds", self._mediaserver_service, elapsed_time)
            if elapsed_time > timeout_sec:
                self._server_failed_to_start = True
            time.sleep(1)

    def install(self, installer):
        self.run_installer(installer)
        self.discard_tray_assistant()
        self._wait_for_server_service_started()
        if not self.is_valid():
            raise RuntimeError(f"{self!r} is invalid when just installed")

    def _list_installer_log_files(self, customization=None):
        if customization is None:
            customization = self._customization()
        server_display_name = customization.windows_server_display_name.replace(' ', '_')
        client_display_name = customization.windows_client_display_name.replace(' ', '_')
        bundle_display_name = customization.windows_bundle_display_name.replace(' ', '_')
        all_logs = []
        all_logs.append(self._installer_logs_dir.glob(f'{server_display_name}*log'))
        all_logs.append(self._installer_logs_dir.glob(f'{client_display_name}*log'))
        all_logs.append(self._installer_logs_dir.glob(f'{bundle_display_name}*log'))
        return list(all_logs)

    def run_installer(self, installer: RemotePath):
        try:
            self._run_installer_command(installer)
        except CalledProcessError as e:
            if e.returncode == 1:
                [*_, last_log_file] = self._list_installer_log_files()
                remote_log = last_log_file.read_text()
                if 'package is for another cloud instance' in remote_log:
                    raise AnotherCloud()
            raise CannotInstall(str(e))
        if not self._list_installer_log_files():
            raise RuntimeError("Cannot find logs after being installed")

    def get_binary_path(self) -> RemotePath:
        return self._executable

    def is_valid(self):
        return all([
            self._build_info_file.exists(),
            self.get_binary_path().exists(),
            self.os_access.registry.key_exists(self._config_key),
            ])
