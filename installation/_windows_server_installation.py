# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import functools
import logging
import subprocess
import time
from subprocess import CalledProcessError
from uuid import UUID

from distrib import BuildInfoError
from distrib import Customization
from distrib import PathBuildInfo
from distrib import known_customizations
from installation._base_installation import CannotInstall
from installation._base_installation import OsNotSupported
from installation._base_installation import _NotInstalled
from installation._debugger import WindowsDebugger
from installation._mediaserver import AnotherCloud
from installation._mediaserver import Mediaserver
from installation._mediaserver import ServerGuidNotFound
from installation._windows_installation import WindowsInstallation
from os_access import CannotDelete
from os_access import RemotePath
from os_access import WindowsAccess
from os_access._windows_registry import ValueNotFoundError

_logger = logging.getLogger(__name__)


class WindowsServerInstallation(Mediaserver, WindowsInstallation):
    """Manage installation on Windows."""

    _customization_by_display_name = {
        c.windows_server_display_name: c
        for c in known_customizations.values()
        if c.windows_server_display_name is not None}

    def __init__(self, os_access: WindowsAccess, customization: Customization):
        if not isinstance(os_access, WindowsAccess):
            raise OsNotSupported(self.__class__, os_access)
        program_files_dir = os_access.program_files_dir()
        system_profile_dir = os_access.system_profile_dir()
        user_profile_dir = os_access.home()
        self._system_local_app_data = system_profile_dir / 'AppData' / 'Local'
        self._installer_logs_dir = user_profile_dir / 'AppData' / 'Local' / 'Temp'
        self._various_files_dir = os_access.fs_root() / 'FT'
        self._various_files_dir.mkdir(exist_ok=True)
        self._server_logs_dir = self._system_local_app_data / customization.windows_server_app_data_subdir / 'log'
        super(WindowsServerInstallation, self).__init__(
            os_access=os_access,
            dir=program_files_dir / customization.windows_server_installation_subdir,
            binary_dir='',
            var_dir=self._system_local_app_data / customization.windows_server_app_data_subdir,
            default_archive_dir=os_access.path('C:\\', customization.storage_dir_name),
            archive_dir_name=customization.storage_dir_name,
            core_dumps_dirs=[
                self._system_local_app_data,  # Crash dumps written here.
                user_profile_dir,  # Manually created with `procdump`.
                user_profile_dir / 'AppData' / 'Local' / 'Temp',  # From task manager.
                ],
            core_dump_glob='mediaserver*.dmp',
            username='LocalSystem',
            )
        self._config_key = customization.windows_server_registry_key
        self._debugger = WindowsDebugger(self.os_access)

    @classmethod
    def find(cls, os_access: WindowsAccess) -> "WindowsServerInstallation":
        if not isinstance(os_access, WindowsAccess):
            raise OsNotSupported(cls, os_access)
        for _, customization in known_customizations.items():
            install_dir = os_access.program_files_dir() / customization.windows_server_installation_subdir
            filename = install_dir / 'build_info.txt'
            try:
                build_info = PathBuildInfo(filename)
            except FileNotFoundError:
                _logger.info("Not found build_info.txt at %s", str(install_dir))
                continue
            except BuildInfoError as err:
                _logger.info("Error due read %s (%s)", str(filename), str(err))
                continue
            _logger.info("Installation was found at %s", str(install_dir))
            return cls(os_access, build_info.customization())
        raise _NotInstalled("No installation of VMs was found.")

    def _get_ini_dir(self):
        return self._system_local_app_data / 'nx_ini'

    def _get_event_log_error_records(self):
        # Failures from Service Control Manager go in pairs.
        specific_error_record = None
        generic_error_record = None
        event_log = self.os_access.winrm.wsman_select('Win32_NTLogEvent', {'LogFile': 'System'})
        while True:
            # Records are sorted from latest to oldest. We need only one or two of latest records
            # to extract error.
            try:
                [_, record] = next(event_log)
            except StopIteration:
                break
            if record['SourceName'] != 'Service Control Manager':
                continue
            if 'Network Optix Media Server' not in record['Message']:
                continue
            generic_error_record = record
            if record['EventCode'] == '7000':
                # 7000 is an event with generic service startup failure description.
                # Next record should have more specific error about this failure.
                [_, specific_error_record] = next(event_log)
                if 'Network Optix Media Server' not in specific_error_record['Message']:
                    specific_error_record = None
            break
        return generic_error_record, specific_error_record

    def _get_mediaserver_exe_error(self):
        binary_path = self.get_binary_path()
        try:
            self.os_access.run(str(binary_path))
        except CalledProcessError as e:
            message = f"{binary_path} failed with error code {e.returncode};\n"
            stdout = e.stdout.decode('ascii')
            stderr = e.stderr.decode('ascii')
            if not stderr and not stdout:
                # If error is shown in message box - there is no way to catch or redirect it.
                # Binary file should be launched manually from cmd to see error in message box.
                message += (
                    f"Error message appears in message box. Launch {binary_path} manually "
                    "to see it or try to find error code description.")
            else:
                message += f"stdout: {stdout or None}\nstderr: {stderr or None}\n"
            return message
        else:
            return f"{binary_path} exited normally."

    def _get_error_on_server_start(self):
        # Service Control Manager swallows actual error from executable and produces error messages
        # of its own, which can be misleading under certain circumstances.
        started_at = time.monotonic()
        # Records from SCM can appear with delay, so retry if no events are found
        while time.monotonic() - started_at < 10:
            [generic_error_record, specific_error_record] = self._get_event_log_error_records()
            if generic_error_record is not None:
                break
            time.sleep(1)
        else:
            return (
                "Service was not running after installation; failed to get comprehensive error, "
                "further investigation is needed.")
        if specific_error_record is None:
            return (
                "Service was not running after installation; failed to get comprehensive "
                f"specific error; general error description: {generic_error_record['Message']}; "
                "further investigation is needed.")
        if specific_error_record['EventCode'] == '7009':
            # 7009 is a timeout event. SCM waits for service to connect, if it doesn't - timeout
            # event is generated. But same event is generated for ANY binary execution failure.
            # To get actual error reason mediaserver.exe should be launched manually to inspect
            # return code, stdout and stderr.
            mediaserver_exe_error = self._get_mediaserver_exe_error()
            return (
                f"SCM reports that {specific_error_record['Message']!r}. "
                "This message can be misleading.\n"
                f"Error on binary file execution:\n{mediaserver_exe_error}")
        return (
            f"General error description: {generic_error_record['Message']}; "
            f"Specific error description: {specific_error_record['Message']};"
            "Error code from launching mediaserver.exe: "
            f"{specific_error_record['EventIdentifier']}")

    def _start(self, already_started_ok=False):
        _logger.info('Start %s', self)
        service = self.service
        if service.is_running():
            if not already_started_ok:
                raise Exception("Already started")
        else:
            service.start()

    def _stop(self, already_stopped_ok=False):
        self._stop_single_service(
            self.service, already_stopped_ok=already_stopped_ok)

    def get_binary_path(self):
        return self._binary_dir / 'mediaserver.exe'

    def is_valid(self):
        return all([
            self._build_info_file.exists(),
            self.os_access.registry.key_exists(self._config_key),
            ])

    @property
    @functools.lru_cache()
    def service(self):
        service_name = self._customization().windows_server_service_name
        return self.os_access.service(service_name)

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
    def _discard_tray_assistant(self):
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

    def install(self, installer):
        self.run_installer(installer)
        self._discard_tray_assistant()
        self._wait_for_service_started()
        if not self.is_valid():
            raise RuntimeError(f"{self!r} is invalid when just installed")

    def run_installer(self, installer: RemotePath):
        try:
            self._run_installer_command(installer)
        except CalledProcessError as e:
            if e.returncode == 1:
                [*_, last_log_file] = self.list_installer_log_files()
                remote_log = last_log_file.read_text()
                if 'package is for another cloud instance' in remote_log:
                    raise AnotherCloud()
            raise CannotInstall(str(e))
        if not self.list_installer_log_files():
            raise RuntimeError("Cannot find logs after being installed")

    def _save_backtrace(self, pid, path):
        self._debugger.save_backtrace(pid, path)

    def parse_core_dump(self, path):
        return self._debugger.parse_core_dump(path)

    def get_mediaserver_guid(self):
        try:
            return UUID(self.os_access.registry.get_string(self._config_key, 'serverGuid'))
        except ValueNotFoundError:
            raise ServerGuidNotFound()

    def get_main_log_level(self):
        return self.os_access.registry.get_string(self._config_key, 'mainLogLevel')

    def update_conf(self, new_configuration):
        for name, value in new_configuration.items():
            if value is None:
                self.os_access.registry.delete_value(self._config_key, name)
            elif isinstance(value, str):
                self.os_access.registry.set_string(self._config_key, name, value)
            elif isinstance(value, int):
                if 'time' in name.lower() or 'space' in name.lower():
                    self.os_access.registry.set_qword(self._config_key, name, value)
                else:
                    self.os_access.registry.set_dword(self._config_key, name, value)

    def _clean_up_server_logs(self):
        files = self._server_logs_dir.iterdir()
        for file in files:
            try:
                file.unlink(missing_ok=True)
            except PermissionError:
                _logger.info("No permission to remove file %s", file)

    def _remove_old_mediaserver_dumps(self):
        for dump in self.list_core_dumps():
            dump.unlink(missing_ok=True)

    def clean_up_outdated_artifacts(self):
        self._clean_up_server_logs()
        self._clean_up_parsed_backtraces()
        self._remove_old_mediaserver_dumps()
        self._clean_installer_system_logs()

    def list_installer_log_files(self, customization=None):
        if customization is None:
            customization = self._customization()
        display_name = customization.windows_server_display_name.replace(' ', '_')
        return list(self._installer_logs_dir.glob(f'{display_name}*log'))
