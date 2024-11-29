# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from datetime import datetime
from subprocess import CalledProcessError
from subprocess import TimeoutExpired
from typing import Collection
from typing import Mapping
from typing import Sequence
from uuid import uuid4

from distrib import Customization
from distrib import Version
from distrib import known_customizations
from gui.testkit import TestKit
from installation._base_installation import CannotInstall
from installation._base_installation import OsNotSupported
from installation._client_configuration import ClientStateDirectory
from installation._debugger import WindowsDebugger
from installation._ini_config import read_ini
from installation._windows_installation import WindowsInstallation
from os_access import CannotDelete
from os_access import RemotePath
from os_access import WindowsAccess
from os_access import copy_file
from os_access.windows_graphic_app import start_in_graphic_mode

_logger = logging.getLogger(__name__)


class WindowsClientInstallation(WindowsInstallation):
    _customization_by_display_name = {
        c.windows_client_display_name: c
        for c in known_customizations.values()
        if c.windows_client_display_name is not None}

    def __init__(
            self,
            os_access: WindowsAccess,
            installer_customization: Customization,
            installer_version: Version,
            ):
        if not isinstance(os_access, WindowsAccess):
            raise OsNotSupported(self.__class__, os_access)
        program_files_dir = os_access.program_files_dir()
        dir = program_files_dir / installer_customization.windows_client_installation_subdir / str(installer_version)
        super().__init__(os_access, dir)
        self._executable = dir / (installer_customization.windows_client_executable + '.exe')
        self._config_key = installer_customization.windows_client_registry_key
        self._various_files_dir = os_access.fs_root() / 'FT'
        self._various_files_dir.mkdir(exist_ok=True)
        home = self.os_access.home()
        self._local_app_data = home / 'AppData' / 'Local'
        self._app_data = self._local_app_data / 'Network Optix' / 'Network Optix HD Witness Client'
        self._settings_dir = self._app_data / 'settings'
        self._local_settings_dir = self._settings_dir / 'local'
        self._client_core_dir = self._settings_dir / 'client_core'
        self._nx_ini = self._local_app_data / 'nx_ini'
        self.archive_dir = home / 'Videos' / 'HD Witness Media'
        self._installer_logs_dir = self._local_app_data / 'Temp'
        self._debugger = WindowsDebugger(self.os_access)

    @classmethod
    def find_installation(cls, os_access: WindowsAccess) -> 'WindowsClientInstallation':
        # This method may be useful for external scripts
        found = cls.find_installations(os_access)
        if len(found) == 0:
            raise RuntimeError("Windows VMS Client: Not installed")
        if len(found) >= 2:
            raise RuntimeError(f"Windows VMS Client: Multiple installations found: {found}")
        [first, *_] = found
        return first

    @classmethod
    def find_installations(cls, os_access: WindowsAccess) -> Collection['WindowsClientInstallation']:
        # This method may be useful for external scripts
        return [
            cls(os_access, customization, version)
            for [customization, version, _uninstall_str]
            in cls._find_registry_entries(os_access)
            ]

    def is_valid(self) -> bool:
        if not self._build_info_file.exists():
            logging.warning("Build info file %s does not exist", self._build_info_file)
            return False
        elif not self.get_binary_path().exists():
            logging.warning("Client executable %s is not found", self.get_binary_path())
            return False
        elif self.older_than('vms_6.0'):
            if not self.os_access.registry.key_exists(self._config_key):
                logging.warning("Client version is less than 6.0, but a registry key %s is absent", self._config_key)
                return False
        return True

    def prepare_and_start(self, command_line: Sequence[str]):
        self._disable_certificate_validation()
        self._pre_accept_eula()
        self._initialize_testkit()
        _logger.info("Start application")
        # Start client without beta messages.
        self.start([
            '--no-single-application',
            *command_line,
            ])
        _logger.debug("Application started")

    def start(self, command_line: Sequence[str]):
        start_in_graphic_mode(self.os_access, [
            str(self.get_binary_path()),
            *command_line,
            ])

    def stop_all_instances(self):
        self.os_access.kill_all_by_name(self.get_binary_path().name)

    def get_binary_path(self) -> RemotePath:
        return self._executable

    def _initialize_testkit(self):
        os_access = self.os_access
        contents = []
        client_ini = os_access.home() / 'AppData' / 'Local' / 'nx_ini' / 'desktop_client.ini'

        if client_ini.exists():
            for line in client_ini.read_text().splitlines():
                if 'clientWebServer' not in line:
                    contents.append(line)
        else:
            client_ini.parent.mkdir(parents=True, exist_ok=True)
        contents.append('clientWebServerPort=7012')
        contents.append('clientWebServerHost="0.0.0.0"')
        client_ini.write_text('\n'.join(contents))

    def _disable_certificate_validation(self):
        self.os_access.registry.create_key(
            r'HKCU\SOFTWARE\Network Optix\Network Optix HD Witness Client\client_core',
            )
        self.os_access.registry.set_string(
            r'HKCU\SOFTWARE\Network Optix\Network Optix HD Witness Client\client_core',
            'CertificateValidationLevel',
            '"disabled"',
            )

    def install(self, installer):
        try:
            self._run_installer_command(installer)
        except CalledProcessError as e:
            raise CannotInstall(str(e))
        if not self.is_valid():
            raise RuntimeError(f"{self!r} is invalid when just installed")

    def set_ini(self, name, values: Mapping[str, str]):
        self._nx_ini.mkdir(exist_ok=True)
        try:
            current_values = read_ini(self._nx_ini / name)
        except FileNotFoundError:
            _logger.info(f'File {name} not found. It will be created.')
            current_values = {}
        all_values = {
            **current_values,
            **values,
            }
        content = []
        for option, value in all_values.items():
            content.append(f'{option}={value}')
        ini_path = self._nx_ini / name
        ini_path.write_text('\n'.join(content))

    def remove_ini(self, name):
        ini_file_path = self._nx_ini / name
        try:
            ini_file_path.unlink()
        except FileNotFoundError:
            _logger.info('File %s not found so cannot be removed', ini_file_path)

    def kill_client_process(self):
        self.os_access.kill_all_by_name('HD Witness.exe')

    def state_dir(self):
        return ClientStateDirectory(self._app_data / 'state')

    def _write_log_ini(self, config):
        self._nx_ini.mkdir(exist_ok=True)
        path = self._nx_ini / 'desktop_client_log.ini'
        path.write_text(config)

    def setup_full_crash_dump(self):
        (self._local_settings_dir / 'createFullCrashDump').write_text('true')

    def connect_testkit(self, timeout: float = 20, testkit_port: int = 7012) -> TestKit:
        _logger.info('Connect to TestKit')
        testkit = TestKit(self.os_access.address, testkit_port)
        testkit.connect(timeout)
        testkit.reset_cache()
        return testkit

    def _pre_accept_eula(self):
        _logger.info("Pre-accept EULA in settings")
        (self._local_settings_dir / 'acceptedEulaVersion').write_text('1')

    def clean_installer_local_user_logs(self):
        for log_file in self._list_installer_log_files():
            _logger.info("Remove old installer log file: %s", log_file)
            log_file.unlink(missing_ok=True)

    def _clean_nx_ini_dir(self):
        try:
            self._nx_ini.rmtree()
        except FileNotFoundError:
            _logger.info("No folder nx_ini found")
        self._nx_ini.mkdir(exist_ok=True)

    def configure_for_tests(self):
        """Configure clean client to investigate bugs easier."""
        # .ini files are not part of config and not touched by installer.
        # But they're set up for tests.
        # That's why they're not removed in .clean_up() but removed here.
        self._clean_nx_ini_dir()
        self.create_desktop_client_log_ini(verbose=True)
        self._app_data.mkdir(exist_ok=True, parents=True)
        self._settings_dir.mkdir(exist_ok=True)
        self._local_settings_dir.mkdir(exist_ok=True)
        self._client_core_dir.mkdir(exist_ok=True)
        # By default, value of storeFrameTimePoints is 1000.
        self.set_ini("desktop_client.ini", {"storeFrameTimePoints": "99999"})

    def create_desktop_client_log_ini(self, verbose: bool):
        content = (
            '[General]\n'
            'logArchiveSize=10\n'
            'maxLogFileSize=10485760\n'
            '[client_log]\n'
            'debug=*\n'
            'none=re:^nx::vms::discovery|permissions\n'
            '[permissions_log]\n'
            'verbose=re:permissions\n'
            'always=*\n'
            '[http_log]\n'
            'verbose=HTTP\n'
            'always=*\n'
            '[file_transfer]\n'
            'verbose=nx::vms::common::p2p::downloader,'
            'nx::vms::client::desktop::UploadWorker\n'
            '[client_updates]\n'
            'verbose=nx::vms::client::desktop::ClientUpdateTool,\\\n'
            '\tnx::vms::client::desktop::ServerUpdateTool,\\\n'
            '\tCompatibilityVersionInstallationDialog\n'
            )
        if verbose:
            content += (
                '[verbose_log]\n'
                'verbose=*\n'
                )
        self._write_log_ini(content)

    def collect_artifacts(self, artifacts_path):
        logs_dir = self._app_data / 'log'
        for file in logs_dir.glob('*'):
            if file.exists():
                copy_file(file, artifacts_path / file.name)
        if len(self.list_core_dumps()) != 0:
            self._parse_core_dumps(artifacts_path)
        for log_file in self._list_installer_log_files():
            copy_file(log_file, artifacts_path / log_file.name)

    def _list_installer_log_files(self):
        display_name = self._customization().windows_client_display_name.replace(' ', '_')
        return list(self._installer_logs_dir.glob(f'{display_name}*log'))

    def _remove_crash_dumps(self):
        for dump in self.list_core_dumps():
            dump.unlink()

    def list_core_dumps(self):
        return [path for path in self._local_app_data.glob('*.dmp')]

    def _parse_core_dumps(self, artifactory_dir):
        for core_dump in self.list_core_dumps():
            _logger.info('Parsing of dump %s started', core_dump)
            parsed_dump_name = core_dump.name + '.backtrace.txt'
            traceback_file = artifactory_dir / parsed_dump_name
            try:
                traceback = self._debugger.parse_core_dump(core_dump)
                traceback_file.write_bytes(traceback)
                _logger.info('Parsing of dump %s finished', core_dump)
            except Exception:
                _logger.exception('Cannot parse core dump: %s', core_dump)

    def take_backtrace(self, artifacts_dir):
        name = self._customization().windows_client_executable
        file_name = (
            f'{datetime.now():%Y%m%d_%H%M%S}-'
            'HDWitness.exe.backtrace.txt')
        traceback_file = artifacts_dir / file_name
        try:
            pid = self.os_access.get_pid_by_name(name)
        except TimeoutExpired:
            _logger.info('%r: Cannot take backtrace from client', self)
            return
        except FileNotFoundError:
            _logger.info('%r: Cannot take backtrace from stopped client', self)
            return
        self._debugger.save_backtrace(pid, traceback_file)

    def reset_all_client_settings(self):
        if self._app_data.exists():
            _logger.debug("Cleaning current client installation")
            try:
                self._app_data.rmtree()
            except CannotDelete as e:
                [_error_code, message] = e.args
                _logger.info(
                    "Failed to delete folder.\n"
                    "Maybe it's not yet released by previously closed client.\n"
                    "Wait for some time and try again.\n"
                    "Error message: %s",
                    message)
                time.sleep(5)
                self._app_data.rmtree()

    def add_fake_welcome_screen_tiles(self, n: int):
        """Do this before starting the AUT, but after cleaning AUT settings.

        Each tile must have different uuid4 key.
        """
        path = self._client_core_dir / 'recentLocalConnections'
        data = ""
        for i in range(n):
            data += f'"{{{uuid4()}}}":{{"systemName":"SQUISH_FAKE{i}","urls":["//localhost:7001"]}}'
            if i != n - 1:
                data += ','
        result = '{' + data + '}'
        path.write_text(result)

    def temp_dir(self):
        temp_dir = self.os_access.home() / 'squish_server_temp'
        temp_dir.mkdir(exist_ok=True)
        return temp_dir

    def is_running(self) -> bool:
        name = self._customization().windows_client_executable
        try:
            self.os_access.get_pid_by_name(name)
        except FileNotFoundError:
            return False
        else:
            return True
