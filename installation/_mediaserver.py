# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import base64
import io
import ipaddress
import logging
import socket
import tempfile
import time
import traceback
import zipfile
from abc import ABCMeta
from abc import abstractmethod
from collections.abc import Collection
from collections.abc import Container
from collections.abc import Iterable
from collections.abc import Mapping
from collections.abc import Sequence
from contextlib import AbstractContextManager
from contextlib import contextmanager
from datetime import datetime
from ipaddress import ip_network
from pathlib import Path
from subprocess import CalledProcessError
from subprocess import TimeoutExpired
from typing import Any
from typing import Optional
from typing import Union
from urllib.parse import urlparse
from uuid import UUID

from distrib import SpecificFeatures
from distrib import known_customizations
from doubles.video.ffprobe import SampleMediaFile
from installation._base_installation import BaseInstallation
from installation._debugger import DebuggerNotFound
from installation._ini_config import update_ini
from installation._nxdb import Nxdb
from installation._remote_directory import RemoteDirectory
from installation._video_archive import MediaserverArchive
from mediaserver_api import MediaserverApi
from mediaserver_api import MediaserverApiConnectionError
from mediaserver_api import MediaserverApiHttpError
from mediaserver_api import Testcamera
from os_access import OsAccess
from os_access import RemotePath
from os_access import Service
from os_access import ServiceFailedDuringStop
from os_access import ServiceNotFoundError
from os_access import ServiceRecoveredAfterStop
from os_access import ServiceStartError
from os_access import ServiceStatusError
from os_access import ServiceUnstoppableError
from os_access import copy_file

_logger = logging.getLogger(__name__)


class AnotherCloud(Exception):
    pass


class MediaserverHangingError(Exception):
    pass


class MediaserverExaminationError(Exception):
    pass


class _MediaserverRecoveredAfterStop(Exception):
    pass


class _MediaserverFailedDuringStop(Exception):
    pass


class _Backup:

    def __init__(self, path):
        self.path = path
        [self.prefix, build_str, timestamp_ms_str, self.reason] = path.stem.split('_', 3)
        self.suffix = path.suffix
        self.timestamp_sec = float(timestamp_ms_str) / 1000
        self.build = int(build_str)
        self._identity = (self.prefix, self.build, self.timestamp_sec, self.reason, self.suffix)

    def __repr__(self):
        return f'<_Backup {self.path}>'

    def __eq__(self, other):
        if not isinstance(other, _Backup):
            return NotImplemented
        return self._identity == other._identity

    def filename(self) -> str:
        return self.path.name

    def size(self) -> int:
        return self.path.stat().st_size

    def base64(self) -> bytes:
        return base64.encodebytes(self.path.read_bytes())

    def content(self) -> bytes:
        return self.path.read_bytes()


# Mediaserver sends requests to these resources to get its public IP address.
# If IP is received, mediaserver sets the SF_HasPublicIP (before APIv4) or
# hasInternetConnection (APIv4) flag (can be received via api/moduleInformation)
public_ip_check_addresses = ('tools.vmsproxy.com', 'tools-eu.vmsproxy.com')

time_server = 'instance1.rfc868server.com'


class Mediaserver(BaseInstallation, metaclass=ABCMeta):
    """Install and access installed files in uniform way."""

    def __init__(
            self,
            os_access: OsAccess,
            dir,
            binary_dir,
            var_dir,
            default_archive_dir,
            archive_dir_name,
            core_dumps_dirs,
            core_dump_glob,
            username,
            ):
        super().__init__(os_access, dir)
        self._binary_dir = dir / binary_dir  # type: RemotePath
        self._lib_dir = dir / 'lib'  # type: RemotePath
        self._var = dir / var_dir  # type: RemotePath
        self._log_dir = self._var / 'log'  # type: RemotePath
        self.ecs_db = self._var / 'ecs.sqlite'  # type: RemotePath
        self.mserver_db = self._var / 'mserver.sqlite'  # type: RemotePath
        self._key_pair_file = self._var / 'ssl' / 'cert.pem'
        self._archive_dir_name = archive_dir_name
        self._backup_dir: RemotePath = self._var / 'backup'
        self.updates_dir = self._var / 'downloads' / 'updates'
        self.default_archive_dir = default_archive_dir
        self._core_dumps_dirs = [dir / core_dumps_dir for core_dumps_dir in core_dumps_dirs]
        self._core_dump_glob = core_dump_glob  # type: str
        self._appropriately_stopped = True
        self.port = 7001
        self._server_failed_to_start = False
        self.username = username
        self.api = None

    @abstractmethod
    def _get_ini_dir(self) -> Path:
        pass

    @abstractmethod
    def _start(self, already_started_ok=False):
        pass

    def _wait_until_online(self):
        started_at = time.monotonic()
        while True:
            if self.api.is_online():
                break
            if time.monotonic() - started_at > 120:
                raise TimeoutError("Timed out waiting for Mediaserver to get online")
            time.sleep(2)

    def start(self, already_started_ok=False):
        self._appropriately_stopped = False
        try:
            self._start(already_started_ok=already_started_ok)
        except ServiceStartError as e:
            self._server_failed_to_start = True
            error_message = str(e)
            error_cause = self._get_error_on_server_start()
            raise RuntimeError(
                f"{self.service} error on start:\n"
                f"Error message from service: {error_message}\n"
                f"Possible error cause: {error_cause}")
        self._wait_until_online()

    def _stop_single_service(self, service, already_stopped_ok=False):
        _logger.info("Stop service %s", service)
        status = service.status()
        if not status.is_stopped:
            if status.is_running:
                try:
                    service.stop(timeout_sec=30)
                except ServiceUnstoppableError:
                    _logger.error("%s couldn't stop. Will take core dump in collect_artifacts().", service)
                    raise MediaserverHangingError("Cannot stop %s service", service)
                except ServiceFailedDuringStop:
                    _logger.error("An error occurred while stopping %s.", service)
                    raise _MediaserverFailedDuringStop(f"Failed to stop {service}")
                except ServiceRecoveredAfterStop:
                    _logger.error(
                        "%s recovered after stopping. This could be caused"
                        "by a crash during the stop.",
                        service)
                    raise _MediaserverRecoveredAfterStop(f"Failed to stop {service}")
            started_at = time.monotonic()
            while True:
                if service.is_stopped():
                    break
                if time.monotonic() - started_at > 130:
                    raise TimeoutError("Timed out waiting for service to stop")
                time.sleep(2)
        elif not already_stopped_ok:
            raise RuntimeError("Already stopped")

    @abstractmethod
    def _stop(self, already_stopped_ok=False):
        pass

    def stop(self, already_stopped_ok=False):
        self._appropriately_stopped = True
        self._stop(already_stopped_ok=already_stopped_ok)

    @property
    @abstractmethod
    def service(self) -> Service:
        pass

    @abstractmethod
    def get_mediaserver_guid(self) -> UUID:
        pass

    @abstractmethod
    def update_conf(self, new_configuration: Mapping[str, Optional[Union[int, str]]]):
        pass

    def list_log_files(self, mask='*') -> Collection[RemotePath]:
        logs_dir = self._log_dir
        if logs_dir.exists():
            return list(logs_dir.glob(mask))
        else:
            return []

    @contextmanager
    def downloaded_log_files(self, mask='*') -> AbstractContextManager[Iterable[Path]]:
        with tempfile.TemporaryDirectory() as td:
            temp_dir = Path(td)
            for log_file in self.list_log_files(mask):
                if log_file.suffix == '.zip':
                    with zipfile.ZipFile(io.BytesIO(log_file.read_bytes()), 'r') as zfp:
                        [archived_log] = zfp.filelist
                        rotated_name = log_file.name.replace('.log.zip', '.log')
                        archived_log.filename = rotated_name
                        zfp.extract(archived_log, temp_dir)
                else:
                    copy_file(log_file, temp_dir / log_file.name)
            yield temp_dir.iterdir()

    @abstractmethod
    def list_installer_log_files(self, customization=None) -> Collection[RemotePath]:
        pass

    def list_core_dumps(self) -> Collection[RemotePath]:
        return [
            path
            for dir in self._core_dumps_dirs
            for path in dir.glob(self._core_dump_glob)
            ]

    @abstractmethod
    def parse_core_dump(self, path) -> bytes:
        pass

    def init_key_pair(self, key_pair: str = ''):
        _logger.info("Put key pair to %s.", self._key_pair_file)
        self._key_pair_file.parent.mkdir(parents=True, exist_ok=True)
        self._key_pair_file.write_text(key_pair)

    def remove_database_backups(self):
        if self._backup_dir.exists():
            _logger.info("Remove backup files.")
            for backup_file in self._backup_dir.glob('ecs_*.db'):
                backup_file.unlink()

    def _remove_ssl_certificates_backups(self):
        if self._backup_dir.exists():
            _logger.info("Remove SSL Certificates backups.")
            ssl_dir = self._backup_dir / 'ssl'
            ssl_dir.rmtree(ignore_errors=True)

    def clean_up_installer_log_files(self, customization=None):
        for log_file in self.list_installer_log_files(customization):
            _logger.info("Remove old installer log file: %s", log_file)
            log_file.unlink()

    def specific_features(self) -> SpecificFeatures:
        path = self.dir / 'specific_features.txt'
        raw = path.read_bytes()
        return SpecificFeatures(raw)

    def update_ini(self, name, new_values: Mapping[str, Any]):
        path = self._get_ini_dir() / (name + '.ini')
        update_ini(path, new_values)

    def enable_saving_console_output(self):
        ini_dir = self._get_ini_dir()
        ini_dir.mkdir(parents=True, exist_ok=True)
        _logger.debug("Zero out mediaserver_stdout.log and mediaserver_stderr.log")
        (ini_dir / 'mediaserver_stdout.log').write_bytes(b'')
        (ini_dir / 'mediaserver_stderr.log').write_bytes(b'')

    def set_cloud_host(self, new_host):
        if not self.service.status().is_stopped:
            raise RuntimeError("Mediaserver must be stopped to patch cloud host.")
        customization_name = self._build_info().customization().customization_name
        customized_cloud = f'{customization_name}:{new_host}'
        self.update_ini('nx_vms_server', {'customizedCloudHost': customized_cloud})

    def reset_default_cloud_host(self):
        cloud_host = self._build_info().cloud_host()
        self.set_cloud_host(cloud_host)

    def default_cloud_host(self) -> str:
        return self._build_info().cloud_host()

    def branch(self) -> str:
        return self._build_info().branch()

    def allow_public_ip_discovery(self):
        self.os_access.networking.allow_hosts([*public_ip_check_addresses])

    def block_public_ip_discovery(self):
        self.os_access.networking.block_hosts([*public_ip_check_addresses])

    def allow_access_to_cloud(self, cloud_host, services_hosts: Collection = ()):
        self.os_access.networking.allow_hosts([cloud_host, *services_hosts])
        self.allow_public_ip_discovery()

    def block_access_to_cloud(self, cloud_host):
        self.os_access.networking.block_hosts([cloud_host])
        self.block_public_ip_discovery()

    def allow_ldap_server_access(self, ldap_host):
        self.os_access.networking.allow_hosts([ldap_host])

    def block_ldap_server_access(self, ldap_host):
        self.os_access.networking.block_hosts([ldap_host])

    def allow_license_server_access(self, url: str):
        ip = self._extract_ip(url)
        port = self._extract_port(url)
        self.os_access.networking.allow_destination(str(ip_network(ip)), 'tcp', port)

    def block_license_server_access(self, url: str):
        ip = self._extract_ip(url)
        port = self._extract_port(url)
        self.os_access.networking.block_destination(str(ip_network(ip)), 'tcp', port)

    @staticmethod
    def _extract_ip(url: str) -> str:
        parsed = urlparse(url)
        try:
            return str(ipaddress.ip_address(parsed.hostname))
        except ValueError:
            attempts = 4
            while True:
                try:
                    return socket.gethostbyname(parsed.hostname)
                except socket.gaierror:
                    if attempts <= 0:
                        raise
                _logger.debug("Cannot resolve hostname: %s", url)
                time.sleep(1)

    @staticmethod
    def _extract_port(url) -> int:
        parsed = urlparse(url)
        if not parsed.hostname:
            raise ValueError(f"Cannot get hostname from URL: {url}")
        if parsed.port:
            return parsed.port
        elif parsed.scheme == 'https':
            return 443
        elif parsed.scheme == 'http':
            return 80
        else:
            raise ValueError(f"No default port for scheme: {url}")

    def allow_time_server_access(self):
        self.os_access.networking.allow_hosts([time_server])
        # Mediaserver receives time from the Internet only if it has access to it.
        # It is determined by the presence of a public IP
        self.allow_public_ip_discovery()

    def block_time_server_access(self):
        self.os_access.networking.block_hosts([time_server])
        self.block_public_ip_discovery()

    def allow_testcamera_discovery(self, discovery_port):
        # test_camera.ini is reloaded on every camera search iteration.
        self.update_ini('test_camera', {'discoveryPort': discovery_port})
        self.os_access.networking.allow_destination('255.255.255.255/32', 'udp', discovery_port)

    def block_testcamera_discovery(self, discovery_port):
        self.os_access.networking.block_destination('255.255.255.255/32', 'udp', discovery_port)

    def _disable_dw_edge_analytics_plugin(self):
        # This plugin works correctly only on Ubuntu 18. An attempt to load it on other OSs
        # ends with a test fail (server does not crash, but an error appears in the log).
        # Since this plugin is not required for tests, it should be disabled.
        self.update_ini('vms_server_plugins', {'disabledNxPlugins': 'dw_edge_analytics_plugin'})

    def disable_update_files_verification(self):
        # During the update, the server checks the signature of the update files.
        # If the signature is not passed, the update process will fail. If the server
        # is built with the local publicationType, no signature file will be generated.
        # In such cases, verification of the signature of update files should be disabled.
        self.update_ini('nx_vms_server', {'skipUpdateFilesVerification': 1})

    def _set_http_logs_state(self, enable: bool):
        log_level = 'VERBOSE' if enable else 'NONE'
        self.update_conf({'httpLogLevel': log_level})

    def _enable_http_logs(self):
        self._set_http_logs_state(enable=True)

    def disable_http_logs(self):
        self._set_http_logs_state(enable=False)

    _error_log_name = 'log_file_error'
    _logging_ini_name = 'nx_vms_server_log.ini'

    def setup_logging_ini(self, enable_log_file_verbose: bool):
        max_log_archive_count = 3  # Maximum number of log files of each type
        max_log_file_size_bytes = 2 * 1024 * 1024 * 1024
        ini_dir = self._get_ini_dir()
        ini_dir.mkdir(parents=True, exist_ok=True)
        logging_ini = ini_dir / self._logging_ini_name
        log_content = [
            '[General]',
            f'logArchiveSize={max_log_archive_count}',
            f'maxLogFileSizeB={max_log_file_size_bytes}',
            # Max size of log file of any kind.
            # Has to be not less than maxLogFileSizeB, otherwise Mediaserver could crash on assert.
            f'maxLogVolumeSizeB={max_log_file_size_bytes}',
            '[log_file_info]',
            'info=*',
            f'[{self._error_log_name}]',
            'error=*',
            # nx::ServerStorageStreamRecorder is needed for test_dismount_nas_after_server_stopped
            'none=START,QnTestCameraStreamReader,nx::ServerStorageStreamRecorder',
            ]
        if enable_log_file_verbose:
            log_content.extend([
                '[log_file_verbose]',
                'verbose=*',
                ])
        logging_ini.write_text('\n'.join(log_content))

    def enable_analytics_logs(self):
        self.update_ini(
            'analytics_logging', {'analyticsLogPath': str(self._log_dir)})

    def save_analytics_plugin_manifests(self):
        self.update_ini(
            'vms_server_plugins', {
                'analyticsManifestOutputPath': str(self._log_dir),
                })

    def remove_logging_ini(self):
        logging_ini = self._get_ini_dir() / self._logging_ini_name
        logging_ini.unlink(missing_ok=True)

    @abstractmethod
    def get_main_log_level(self) -> str:
        pass

    def set_main_log_level(self, level: str):
        logging_ini = self._get_ini_dir() / self._logging_ini_name
        if logging_ini.exists():
            _logger.warning(
                "Custom log level will not work unless %s is present. Make sure it is removed "
                "before starting server",
                self._logging_ini_name)
        self.update_conf({'mainLogLevel': level})

    def set_max_log_file_size(self, limit_bytes: int):
        self.update_conf({'maxLogFileSizeB': limit_bytes})

    def get_error_log(self) -> str:
        path = self._log_dir / f'{self._error_log_name}.log'
        try:
            logs = path.read_text(errors='replace')
        except FileNotFoundError:
            return ''
        return logs

    def check_for_error_logs(self):
        logs = self.get_error_log()
        if not logs:
            return  # Success: no error log entries.
        raise ErrorLogsFound(f"{self}: ERROR logs found:\n" + logs[:1000])

    def examine(self):
        examination_logger = _logger.getChild('examination')
        examination_logger.info("Post-test check for %s", self)
        if self._server_failed_to_start:
            _logger.warning("Mediaserver startup failed, skip examination.")
            return
        try:
            status = self.service.status()
        except ServiceNotFoundError:
            raise MediaserverExaminationError("Mediaserver service not found")
        except ServiceStatusError:
            raise MediaserverExaminationError()
        if status.is_running:
            examination_logger.debug("%s is running.", self)
            if self.api is not None and self.api.is_online():
                examination_logger.debug("%s is online.", self)
            else:
                raise MediaserverExaminationError(
                    f"{self} is not online; see the backtrace")
        else:
            if not status.is_stopped:
                raise MediaserverExaminationError(
                    "Mediaserver service error. It neither running nor stopped")
            if self._appropriately_stopped:
                examination_logger.info("%s is stopped; it's OK.", self)
            else:
                raise MediaserverExaminationError("{} is stopped.".format(self))

    def take_backtrace(self, name):
        status = self.service.status()
        if status.is_stopped:
            _logger.debug("Mediaserver service stopped; cannot take backtrace")
            return
        file_name = (
            f'{datetime.now():%Y%m%d_%H%M%S}-'
            f'{status.pid}-{name}'
            f'{self.orderly_backtrace_suffix}')
        self._backtraces_directory().mkdir(exist_ok=True)
        backtrace_path = self._backtraces_directory() / file_name
        try:
            self._save_backtrace(status.pid, backtrace_path)
        except DebuggerNotFound:
            # Handle case where is no backtrace file
            logging.error(
                "Debugger not found, "
                "please install platform specific debugger.",
                )

    orderly_backtrace_suffix = '.bt.txt'

    @abstractmethod
    def _save_backtrace(self, pid: int, path: RemotePath):
        pass

    def list_backtraces(self) -> Collection[RemotePath]:
        pattern = f'*{self.orderly_backtrace_suffix}'
        return [*self._backtraces_directory().glob(pattern)]

    def _backtraces_directory(self) -> RemotePath:
        return self.os_access.tmp() / 'backtraces'

    def _clean_up_parsed_backtraces(self):
        try:
            self._backtraces_directory().rmtree()
        except FileNotFoundError:
            _logger.info("No backtraces folder found by path %s", self._backtraces_directory())
        self._backtraces_directory().mkdir()

    def _clean_installer_system_logs(self):
        for file in self.os_access.tmp().glob("*Nx_Witness_Server*.log"):
            file.unlink()

    def collect_artifacts(self, artifacts_dir):
        for file in self.list_log_files():
            if file.exists():
                self._copy_to_artifacts(file, artifacts_dir)
        for backtrace in self.list_backtraces():
            self._copy_to_artifacts(backtrace, artifacts_dir)
        for core_dump in self.list_core_dumps():
            backtrace_path = self._make_artifact_path(
                artifacts_dir, core_dump.name + '.backtrace.txt')
            # noinspection PyBroadException
            try:
                backtrace = self.parse_core_dump(core_dump)
                backtrace_path.write_bytes(backtrace)
            except Exception:
                _logger.exception("Cannot parse core dump: %s.", core_dump)
        self._copy_to_artifacts(self.ecs_db, artifacts_dir)
        self._copy_to_artifacts(self.mserver_db, artifacts_dir)
        self._copy_to_artifacts(self._key_pair_file, artifacts_dir)
        for customization in known_customizations.values():
            self._collect_installation_logs(customization, artifacts_dir)
        self._collect_ini_files(artifacts_dir)
        for server_id, db_file in self.list_object_detection_db().items():
            db_dir = artifacts_dir / str(server_id)
            db_dir.mkdir(exist_ok=True)
            self._copy_to_artifacts(db_file, db_dir)

    def _collect_ini_files(self, artifacts_dir: RemotePath):
        ini_dir = self._get_ini_dir()
        try:
            ini_files = list(ini_dir.iterdir())
        except FileNotFoundError:
            logging.info("INI dir %s does not exist. Skip INI collection", ini_dir)
            return
        for file in ini_files:
            self._copy_to_artifacts(file, artifacts_dir)

    def _collect_installation_logs(self, customization, artifacts_dir):
        for file in self.list_installer_log_files(customization):
            self._copy_to_artifacts(file, artifacts_dir)

    def _copy_to_artifacts(self, file, artifacts_dir):
        artifact_file = self._make_artifact_path(artifacts_dir, file.name)
        attempt = 1
        while True:
            # noinspection PyBroadException
            try:
                try:
                    copy_file(file, artifact_file)
                except PermissionError:
                    if attempt > 3:
                        raise
                    attempt += 1
                    time.sleep(0.5)
                else:
                    break
            except Exception:
                error_file = artifact_file.with_name(artifact_file.name + '.exception.txt')
                error_file.write_text(traceback.format_exc())
                break

    def _make_artifact_path(self, artifacts_dir, file_name):
        prefix = self.os_access.netloc().replace(':', '-')
        return artifacts_dir / f'{prefix}-{file_name}'

    def base_url(self) -> str:
        """URL of Mediaserver as seen from the machine where this code runs."""
        forwarded_port = self.os_access.get_port('tcp', self.port)
        forwarded_address = self.os_access.address
        return 'https://{}:{}'.format(forwarded_address, forwarded_port)

    def url(self, host: str) -> str:
        return 'https://{}:{}'.format(host, self.port)

    @abstractmethod
    def _get_error_on_server_start(self):
        # If server did not start after fresh installation - no error is raised by test, so
        # try to get some comprehensive error message from OS logs.
        pass

    def setup(self, installer: RemotePath):
        """Get mediaserver as if it hasn't run before."""
        self.install(installer)
        self.stop(already_stopped_ok=True)
        if self.service.is_running():
            raise RuntimeError("Cannot stop Mediaserver on setup")

    def init_api(self, api_object: MediaserverApi):
        self.api = api_object

    def add_cameras_with_archive(
            self,
            sample_media_file: SampleMediaFile,
            start_times: Iterable[datetime],
            count=1,
            offset=0,
            ) -> Sequence[Testcamera]:
        """A camera resource in the mediaserver DB and video in the archive."""
        """Add camera, create archive for the camera,
        contained chunks with `sample_media_file` started at `start_times`.
        """
        cameras = self.api.add_test_cameras(offset=offset, count=count)
        for start_time in start_times:
            for camera in cameras:
                self.default_archive().camera_archive(camera.physical_id).save_media_sample(
                    start_time, sample_media_file)
        self.api.rebuild_main_archive()
        return cameras

    def wait_for_database_backups(
            self,
            *,
            skip_backups: Container[_Backup] = (),
            timeout_sec=30,
            ) -> Sequence[_Backup]:
        started_at = time.monotonic()
        while True:
            backups = [backup for backup in self.list_database_backups() if backup not in skip_backups]
            if backups:
                return backups
            if time.monotonic() > started_at + timeout_sec:
                raise RuntimeError("Backups didn't appear")
            _logger.info("Backups didn't appear yet")
            time.sleep(1)

    def list_database_backups(self, skip_backups=()) -> Sequence[_Backup]:
        backups = []
        for path in sorted(self._backup_dir.glob('ecs_*.db')):
            backup = _Backup(path)
            if backup not in skip_backups:
                backups.append(backup)
        return backups

    def install_optional_plugins(
            self, plugin_paths: Iterable[Path], destination: Optional[Path] = None):
        if destination is None:
            destination = self._binary_dir / 'plugins_optional'
        destination.mkdir(exist_ok=True)
        for path in plugin_paths:
            if path.is_file():
                copy_file(path, destination / path.name)
            elif path.is_dir():
                # Some plugins, e.g. Stub Analytics Plugin, are composed of many
                # files and subdirectories stored in a directory named after the plugin.
                new_destination = destination / path.name
                self.install_optional_plugins(path.iterdir(), new_destination)
            else:
                RuntimeError(f"{path} is not a file/symlink and not a directory")

    def enable_optional_plugins(self, plugins):
        enabled_nx_plugins_optional = ''
        for plugin in plugins:
            enabled_nx_plugins_optional += f'{plugin}_analytics_plugin,'
        self.update_ini('vms_server_plugins', {
            'enabledNxPluginsOptional': enabled_nx_plugins_optional[:-1]})

    def enable_legacy_rules_engine(self):
        # In VMS-53670 new rules engine introduced. The old engine is turned off by default.
        # These settings are needed to support both versions.
        self.update_ini('nx_vms_rules', {
            'rulesEngine': 'old',
            'fullSupport': 'true',
            })

    def _wait_for_service_started(self):
        started_at = time.monotonic()
        timeout_sec = 10
        _logger.debug("Waiting for server to start for %d seconds", timeout_sec)
        while True:
            if self.service.is_running():
                return
            elapsed_time = time.monotonic() - started_at
            _logger.debug(
                "%s is not started after %.2f seconds", self.service, elapsed_time)
            if elapsed_time > timeout_sec:
                self._server_failed_to_start = True
                error_message = self._get_error_on_server_start()
                raise RuntimeError(
                    f"{self.service} is not running after fresh installation.\n"
                    f"Possible error cause:\n{error_message}")
            time.sleep(1)

    def list_installer_dirs(self) -> Collection[RemotePath]:
        # See: https://gitlab.nxvms.dev/dev/nx/-/blob/master/vms/server/nx_vms_server/src/nx/vms/server/update/update_installer.cpp#L541
        pattern = f'{self._customization().company_id}_installer*'
        return list(self.os_access.tmp().glob(pattern))

    def replace_database(self, database_file: RemotePath):
        self.remove_database()
        self.ecs_db.parent.take_from(database_file)

    def archive(self, path: str) -> MediaserverArchive:
        return self.archive_on_remote(self.os_access, path)

    def nxdb(self, path: str) -> Nxdb:
        try:
            server_guid = self.get_mediaserver_guid()
        except ServerGuidNotFound:
            raise _CannotFindMediaserverArchive()
        video_archive_files = RemoteDirectory(self.os_access.path(path), self.os_access)
        return Nxdb(video_archive_files, str(server_guid))

    def archive_on_remote(self, remote_os_access, remote_path):
        try:
            server_guid = self.get_mediaserver_guid()
        except ServerGuidNotFound:
            raise _CannotFindMediaserverArchive()
        archive_dir = remote_os_access.path(remote_path) / str(server_guid)
        video_archive_files = RemoteDirectory(archive_dir, remote_os_access)
        return MediaserverArchive(video_archive_files)

    def default_archive(self) -> MediaserverArchive:
        return self.archive(str(self.default_archive_dir))

    def _remove_logs(self):
        try:
            log_files = list(self._log_dir.iterdir())
        except FileNotFoundError:
            _logger.info("%s does not exist, nothing to cleanup", self._log_dir)
            return
        for log_file in log_files:
            log_file.unlink(missing_ok=True)

    @abstractmethod
    def clean_up_outdated_artifacts(self):
        pass

    def remove_database(self):
        _logger.info("Remove ecs database %s", self.ecs_db)
        self.ecs_db.unlink(missing_ok=True)

    def remove_data_from_previous_runs(self):
        self.remove_database_backups()
        self.remove_database()
        self._remove_logs()
        self._remove_ssl_certificates_backups()
        self._remove_archive_index_db()

    def _remove_archive_index_db(self):
        try:
            server_nxdb = self.nxdb(str(self.default_archive_dir))
        except _CannotFindMediaserverArchive:
            _logger.warning(
                "Mediaserver archive not found. Archive index db files won't be removed")
        else:
            server_nxdb.remove()

    def clean_auto_generated_config_values(self):
        self.update_conf({
            'authKey': None,
            'reservedStorageBytesForUpdate': None,
            'serverGuid': None,
            'storedMac': None,
            })

    def set_common_config_values(self):
        self.setup_logging_ini(enable_log_file_verbose=True)
        self._enable_http_logs()
        self._disable_dw_edge_analytics_plugin()

    def supports_language(self, language: str) -> bool:
        return language in self._customization().supported_languages

    def analytics_database_size(self) -> int:
        dirs = [
            self.default_archive_dir / str(self.get_mediaserver_guid()) / 'motion_data',
            self.default_archive_dir / str(self.get_mediaserver_guid()) / 'archive',
            ]
        database_size = 0
        for directory in dirs:
            if directory.exists():
                try:
                    database_size += self.os_access.folder_contents_size(directory)
                except (CalledProcessError, TimeoutExpired):
                    _logger.exception("Error while calculating directory %s size", directory)
        return database_size

    def video_archive_size(self) -> int:
        dirs = [
            self.default_archive_dir / str(self.get_mediaserver_guid()) / 'hi_quality',
            self.default_archive_dir / str(self.get_mediaserver_guid()) / 'low_quality',
            ]
        database_size = 0
        for directory in dirs:
            if directory.exists():
                try:
                    database_size += self.os_access.folder_contents_size(directory)
                except (CalledProcessError, TimeoutExpired):
                    _logger.exception("Error while calculating directory %s size", directory)
        return database_size

    def list_object_detection_db(self) -> Mapping[UUID, RemotePath]:
        databases = {}
        guid_glob = '????????-????-????-????-????????????'.replace('?', '[0-9a-fA-F]')
        for parent in self.default_archive_dir.glob(guid_glob):
            db_path = parent.joinpath('object_detection.sqlite')
            if db_path.exists():
                databases[UUID(parent.name)] = db_path
        return databases

    def output_metrics(self):
        for resource_data in self._get_online_metrics():
            logging.info("Metrics: %r", resource_data)

    def _get_online_metrics(self) -> Collection[Mapping]:
        metrics_dump = []
        if self.api is None:
            logging.warning("Cannot get metrics through API. Mediaserver is probably not installed.")
            return []

        try:
            if self.api.auth_type == 'digest':
                self.api.enable_basic_and_digest_auth_for_admin()
            metrics_dump = self.api.get_metrics_for_data_analysis()
        except MediaserverApiHttpError:
            logging.exception("Cannot get metrics through API")
        except MediaserverApiConnectionError:
            logging.exception("Cannot get metrics through API. Mediaserver is probably shut down.")
        return metrics_dump


class ServerGuidNotFound(Exception):
    pass


class _CannotFindMediaserverArchive(Exception):
    pass


class ErrorLogsFound(Exception):
    pass
