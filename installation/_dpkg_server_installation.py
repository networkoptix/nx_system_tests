# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import functools
import logging
from configparser import ConfigParser
from configparser import NoOptionError
from uuid import UUID

from distrib import Customization
from distrib import PathBuildInfo
from distrib import known_customizations
from installation._base_installation import OsNotSupported
from installation._base_installation import _NotInstalled
from installation._config import update_conf_file
from installation._debugger import PosixDebugger
from installation._dpkg_installation import DpkgInstallation
from installation._mediaserver import Mediaserver
from installation._mediaserver import ServerGuidNotFound
from os_access import OsAccess
from os_access import PosixAccess
from os_access import ServiceNotFoundError

_logger = logging.getLogger(__name__)


class DpkgServerInstallation(Mediaserver, DpkgInstallation):
    _known_packages = {
        c.linux_server_package_name: c
        for c in known_customizations.values()
        if c.linux_server_package_name is not None}
    _component_name = 'mediaserver'

    def __init__(self, os_access: OsAccess, customization: Customization, core_dumps_dirs=None):
        if not isinstance(os_access, PosixAccess):
            raise OsNotSupported(self.__class__, os_access)
        dir = os_access.path('/opt', customization.linux_server_subdir)
        super(DpkgServerInstallation, self).__init__(
            os_access=os_access,
            dir=dir,
            binary_dir='bin',
            var_dir=dir / 'var',
            default_archive_dir=dir / 'var' / 'data',
            archive_dir_name=customization.storage_dir_name,
            core_dumps_dirs=core_dumps_dirs or [dir / 'bin'],
            core_dump_glob='core.*',
            username=customization.linux_user,
            )
        self._config = self.dir / 'etc' / 'mediaserver.conf'
        self.posix_access = os_access  # type: PosixAccess
        self._debugger = PosixDebugger(self.posix_access, self._binary_dir / 'gdb', self._lib_dir)

    @classmethod
    def find(cls, os_access: OsAccess) -> "DpkgServerInstallation":
        if not isinstance(os_access, PosixAccess):
            raise OsNotSupported(cls, os_access)
        for _, customization in known_customizations.items():
            install_dir = os_access.path('/opt', customization.linux_server_subdir)
            filename = install_dir / 'build_info.txt'
            try:
                build_info = PathBuildInfo(filename)
            except FileNotFoundError:
                _logger.info("Not found build_info.txt at %s", str(install_dir))
                continue
            _logger.info("Installation was found at %s", str(install_dir))
            return cls(os_access, build_info.customization())
        raise _NotInstalled("No installation of VM was found.")

    @functools.lru_cache()
    def _get_ini_dir(self):
        username = self.service.get_username()
        ini_dir = self.posix_access.home(username) / '.config' / 'nx_ini'
        _logger.debug("Home directory for user %s found, ini config dir is %s", username, ini_dir)
        return ini_dir

    @property
    def _root_tool_service(self):
        service_name = self._customization().linux_root_tool_service_name
        return self.os_access.service(service_name)

    def _start(self, already_started_ok=False):
        _logger.info('Start %s', self)
        service = self.service
        if service.is_running():
            if not already_started_ok:
                raise Exception("Already started")
        else:
            # VMS-31595: Try to work around an ATA issue in VBox by increasing timeout.
            service.start(timeout_sec=30)

    def _stop(self, already_stopped_ok=False):
        try:
            self._stop_single_service(
                self.service, already_stopped_ok=already_stopped_ok)
        finally:
            try:
                self._stop_single_service(
                    self._root_tool_service, already_stopped_ok=already_stopped_ok)
            except ServiceNotFoundError:
                # ARM32 installations has no root tool, so it is ok if service not found.
                pass

    def get_binary_path(self):
        return self._binary_dir / 'mediaserver'

    def is_valid(self):
        return all([
            self._build_info_file.exists(),
            self._config.exists(),
            ])

    def _save_backtrace(self, pid, path):
        self._debugger.save_backtrace(pid, path)

    def parse_core_dump(self, path):
        return self._debugger.parse_core_dump(self.get_binary_path(), path)

    def _get_mediaserver_conf(self):
        config_text = self._config.read_text(encoding='ascii')
        config = ConfigParser()
        config.read_string(config_text)
        return config

    def get_mediaserver_guid(self):
        config = self._get_mediaserver_conf()
        try:
            return UUID(config.get('General', 'serverGuid'))
        except NoOptionError:
            raise ServerGuidNotFound()

    def get_main_log_level(self):
        config = self._get_mediaserver_conf()
        return config.get('General', 'mainLogLevel')

    def update_conf(self, new_configuration):
        update_conf_file(self._config, new_configuration)

    @property
    @functools.lru_cache()
    def service(self):
        service_name = self._customization().linux_server_service_name
        return self.os_access.service(service_name)

    def _get_error_on_server_start(self):
        service_name = self._customization().linux_server_service_name
        systemctl_result = self.os_access.run([
            'systemctl', 'show',
            '-p', 'InvocationID',
            '--value', service_name,
            ])
        invocation_id = systemctl_result.stdout.decode('ascii').strip()
        journalctl_result = self.os_access.run([
            'journalctl',
            '--no-pager',
            '--quiet',
            '--output', 'short-precise',
            f'_SYSTEMD_INVOCATION_ID={invocation_id}',  # filter by last unit invocation id
            '-u', service_name,
            ])
        return journalctl_result.stdout.decode('ascii')

    def install(self, installer):
        core_pattern_file = self.os_access.path('/etc/sysctl.d/60-core-pattern.conf')
        core_pattern_file.write_bytes(b'kernel.core_pattern=core.%t.%p\n')  # Timestamp and pid.
        self._posix_shell.run(['sysctl', '--load', core_pattern_file])
        self.run_installer(installer)
        self._wait_for_service_started()
        if not self.is_valid():
            raise RuntimeError(f"{self!r} is invalid when just installed")

    def clean_up_outdated_artifacts(self):
        raise NotImplementedError(
            "When this method was created only Windows implementation was needed,"
            "as it was used for GUI autotests in cases where mediaserver is installed"
            "on the same real Windows machine where desktop client is installed."
            "Implement separately on other OS if needed.")

    def list_installer_log_files(self, customization=None):
        _logger.debug("Collecting installation logs is not yet implemented on Linux.")
        return []
