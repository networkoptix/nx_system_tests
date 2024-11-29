# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import shlex
import time
from collections.abc import Mapping
from collections.abc import Sequence
from contextlib import AbstractContextManager
from contextlib import ExitStack
from contextlib import contextmanager
from datetime import datetime
from datetime import timedelta
from itertools import chain
from pathlib import Path
from subprocess import CalledProcessError
from typing import Optional

from distrib import Customization
from distrib import Version
from distrib import known_customizations
from gui.testkit import TestKit
from gui.testkit import TestKitConnectionError
from installation._base_installation import OsNotSupported
from installation._dpkg_installation import DpkgInstallation
from os_access import OsAccess
from os_access import PosixAccess
from os_access import RemotePath
from os_access import Run
from os_access import Ssh
from os_access import copy_file

_logger = logging.getLogger(__name__)

_STARTING_X_SERVER_NUMBER = 99
_STARTING_HTTP_PORT = 7013
_X_AUTHORITY_PATH = '/root/.Xauthority'

_CLIENT_READY_TIMEOUT_SEC = 60


@contextmanager
def _run_in_virtual_x_server(
        shell: Ssh,
        command: Sequence[str],
        authority_file: str,
        server_number: int,
        stdout_path: str,
        stderr_path: str,
        env: Mapping[str, str],
        ) -> AbstractContextManager[Run]:
    xvfb_command = [
        'xvfb-run',
        f'--server-num={server_number}',
        f'--auth-file={authority_file}',
        '--server-args=-screen 0 1024x768x24 +extension GLX +render -noreset',
        ]
    # Use string command to redirect stdout and stderr.
    redirect_output = f'1>{shlex.quote(stdout_path)} 2>{shlex.quote(stderr_path)}'
    command_string = shlex.join([*xvfb_command, *command]) + ' ' + redirect_output
    with shell.Popen(command_string, terminal=True, env=env) as run:
        try:
            yield run
        finally:
            try:
                run.terminate()
            except OSError as e:
                if str(e) == 'Socket is closed':  # Raised from paramiko.channel. Not an error.
                    _logger.warning("Error terminating client run: %s", e)
                else:
                    raise


class ClientServerConnectionError(Exception):
    pass


class _ProcessTerminated(Exception):
    pass


class DpkgClientInstallation(DpkgInstallation):
    _known_packages = {
        c.linux_client_package_name: c
        for c in known_customizations.values()
        if c.linux_client_package_name is not None}
    _component_name = 'client'

    def __init__(
            self,
            os_access: OsAccess,
            installer_customization: Customization,
            installer_version: Version,
            cloud_host: Optional[str] = None,
            ):
        if not isinstance(os_access, PosixAccess):
            raise OsNotSupported(self.__class__, os_access)
        dir = os_access.path('/opt') / installer_customization.linux_client_subdir / str(installer_version)
        super().__init__(os_access, dir)
        config_root = os_access.path('/root/.config')
        self._start_script = dir / 'bin/client'
        self._ini_config = config_root / 'nx_ini/desktop_client.ini'
        self._client_core_config = config_root / 'nx_ini/nx_vms_client_core.ini'
        self._client_config = config_root / installer_customization.linux_client_config_path
        self._cloud_host = cloud_host
        self._ssl_dir = self.dir / 'ssl'
        self.os_access.kill_all_by_name('Xvfb')
        if self.is_valid():
            self._original_ini_config = self._ini_config.read_text().splitlines()
        else:
            self._original_ini_config = []
        self._client_data_dir = installer_customization.linux_client_data_dir
        self._client_artifacts_dir = os_access.tmp() / 'nx_client_artifacts'
        self._client_artifacts_dir.mkdir(exist_ok=True, parents=False)

    def install_ca(self, ca: Path):
        self._client_core_config.parent.mkdir(exist_ok=True)
        self._client_core_config.write_text(f'rootCertificatesFolder={self._ssl_dir.absolute()}')
        self._ssl_dir.mkdir(exist_ok=True)
        ca_cert_file = self._ssl_dir / 'ca.pem'
        ca_cert_file.write_text(ca.read_text())

    def _get_client_data_dir(self):
        if self._client_data_dir is None:
            raise RuntimeError("Client data directory is not specified")
        return self.os_access.path(self._client_data_dir)

    def get_binary_path(self):
        return self.dir / 'bin' / 'client-bin'

    def is_valid(self):
        return all([
            self._build_info_file.exists(),
            self.get_binary_path().exists(),
            self._start_script.exists(),
            self._client_config.exists(),
            self._ini_config.exists(),
            ])

    def clean_certificates(self):
        client_data_dir = self._get_client_data_dir()
        connection_dir = client_data_dir / 'certificates' / 'connection'
        autogenerated_dir = client_data_dir / 'certificates' / 'autogenerated'
        for key_file in chain(connection_dir.glob('*.key'), autogenerated_dir.glob('*.key')):
            key_file.unlink()
        for certificate in self._ssl_dir.glob('*.pem'):
            certificate.unlink()

    def install(self, installer):
        self.run_installer(installer)
        self._client_config.parent.mkdir(parents=True, exist_ok=True)
        self._client_config.write_text((
            '[General]\n'
            # Client won't really start until user accepts EULA in modal dialog.
            # This setting allows to skip this.
            'acceptedEulaVersion=9000\n'  # Just large enough to be valid for a long time
            ))
        self._ini_config.parent.mkdir(parents=True, exist_ok=True)

        if self._cloud_host:
            self._original_ini_config.append(f'cloudHost={self._cloud_host}')
        # Show additional info in client error messages if any.
        self._original_ini_config.append('developerMode=1')
        self._ini_config.write_text('\n'.join(self._original_ini_config))
        if not self.is_valid():
            raise RuntimeError(f"{self!r} is invalid when just installed")

    def _make_temporary_ini_file(self, internal_http_server_port):
        # There is no way to pass HTTP port for internal server as a parameter.
        # Workaround is to make temporary ini file directory and pass it as ENV variable.
        temporary_config = self.os_access.tmp().joinpath(
            f'client_on_{internal_http_server_port}_port_config/desktop_client.ini')
        if not temporary_config.exists():
            temporary_config.parent.mkdir(exist_ok=True, parents=True)
            config_content = [
                *self._original_ini_config,
                f'clientWebServerPort={internal_http_server_port}',
                'clientWebServerHost="0.0.0.0"',
                ]
            config_content = [line + '\n' for line in config_content]
            config_content = ''.join(config_content)
            temporary_config.write_text(config_content)
        temporary_core_config = temporary_config.parent / self._client_core_config.name
        temporary_core_config.write_text(self._client_core_config.read_text())
        return temporary_config

    @contextmanager
    def _running(
            self,
            server_url: str,
            internal_http_server_port: int,
            x_server_number: int,
            ) -> AbstractContextManager['_RunningNxClient']:
        client_command = [
            str(self._start_script),
            '--auth', server_url.rstrip('/'),
            ]
        client_ini = self._make_temporary_ini_file(internal_http_server_port)
        file_stem = f'client_{x_server_number}_{datetime.now().isoformat(timespec="microseconds")}'
        with _run_in_virtual_x_server(
                self.os_access.shell,
                client_command,
                _X_AUTHORITY_PATH,
                x_server_number,
                str(self._client_artifacts_dir / f'{file_stem}.stdout'),
                str(self._client_artifacts_dir / f'{file_stem}.stderr'),
                env={
                    'NX_INI_DIR': str(client_ini.parent),
                    # --no-sandbox required when running under root and
                    # it must be passed as environment variable
                    'QTWEBENGINE_CHROMIUM_FLAGS': '--no-sandbox',
                    },
                ) as run:
            running_testkit = self._connect_to_testkit(internal_http_server_port, timeout=20)
            yield _RunningNxClient(
                run,
                self.os_access,
                x_server_number,
                running_testkit,
                self._client_artifacts_dir,
                )

    @contextmanager
    def opened_client(self, testkit_connect_timeout: float) -> AbstractContextManager['_RunningNxClient']:
        client_command = [str(self._start_script)]
        x_server_number = 0
        client_ini = self._make_temporary_ini_file(_STARTING_HTTP_PORT)
        file_stem = f'client_{x_server_number}_{datetime.now().isoformat(timespec="microseconds")}'
        with _run_in_virtual_x_server(
                self.os_access.shell,
                client_command,
                _X_AUTHORITY_PATH,
                x_server_number,
                str(self._client_artifacts_dir / f'{file_stem}.stdout'),
                str(self._client_artifacts_dir / f'{file_stem}.stderr'),
                env={
                    'NX_INI_DIR': str(client_ini.parent),
                    # --no-sandbox required when running under root and
                    # it must be passed as environment variable
                    'QTWEBENGINE_CHROMIUM_FLAGS': '--no-sandbox',
                    },
                ) as run:
            running_testkit = self._connect_to_testkit(
                _STARTING_HTTP_PORT, timeout=testkit_connect_timeout)
            yield _RunningNxClient(
                run,
                self.os_access,
                _STARTING_X_SERVER_NUMBER,
                running_testkit,
                self._client_artifacts_dir,
                )

    @contextmanager
    def many_clients_running(self, server_url: str, client_count):
        with ExitStack() as exit_stack:
            running_clients = []
            for client_index in range(client_count):
                running_client = exit_stack.enter_context(self._running(
                    server_url,
                    _STARTING_HTTP_PORT + client_index,
                    _STARTING_X_SERVER_NUMBER + client_index,
                    ))
                running_clients.append(running_client)
            yield running_clients

    def measure_connection_time(self, server_url: str, connect_timeout):
        with self._running(
                server_url,
                _STARTING_HTTP_PORT,
                _STARTING_X_SERVER_NUMBER) as running_client:
            try:
                running_client.wait_for_start()
                return running_client.measure_connection_time(connect_timeout)
            except _ProcessTerminated:
                return None

    def list_artifacts(self):
        return self._client_artifacts_dir.iterdir()

    def collect_artifacts(self, artifacts_dir: Path):
        prefix = self.os_access.netloc().replace(':', '-')
        for artifact in self.list_artifacts():
            destination = artifacts_dir / f'{prefix}-{artifact.name}'
            copy_file(artifact, destination)

    def _connect_to_testkit(self, http_port: int, timeout: float) -> TestKit:
        try:
            mapped_port = self.os_access.get_port('tcp', http_port)
        except KeyError:
            # HTTP port must be defined in VmType so it is forwarded for runs on VirtualBox.
            # If test is trying to launch client on HTTP port, that is not forwarded - raise
            # comprehensive error.
            raise RuntimeError(
                f"Cannot start client: there is no port {http_port} in {self.os_access} port map")
        testkit = TestKit(self.os_access.address, mapped_port)
        testkit.connect(timeout)
        testkit.reset_cache()
        return testkit


class _RunningNxClient:

    def __init__(
            self,
            run: Run,
            os_access: PosixAccess,
            x_server_number: int,
            running_testkit: TestKit,
            client_artifacts_dir: RemotePath,
            ):
        self._run = run
        self._os_access = os_access
        self._x_server_number = x_server_number
        self._client_artifacts_dir = client_artifacts_dir
        self._api = running_testkit

    def _take_screenshot(self):
        filename = (
            f'x-server-{self._x_server_number}-screenshot-'
            f'{datetime.now().astimezone():%Y-%m-%d-%H-%M-%S}.png')
        remote_path = self._client_artifacts_dir / filename
        # 'import' command is part of 'imagemagick' package
        try:
            self._os_access.shell.run(
                ['import', '-window', 'root', remote_path],
                env=dict(
                    DISPLAY=f':{self._x_server_number}',
                    XAUTHORITY=_X_AUTHORITY_PATH,
                    ),
                )
        except CalledProcessError as e:
            if e.returncode == 1 and b'unable to open X server' in e.stderr:
                _logger.error("Unable to take screenshot: %s", e)
            else:
                raise

    def _wait_for_time_frame_points(self, wait_message, wait_timeout_sec, return_nonempty=False):
        started_at = time.monotonic()
        while True:
            if self._run.returncode is not None:
                raise _ProcessTerminated(f"Process terminated with code {self._run.returncode}")
            try:
                frame_points = self._api.get_time_frame_points()
            except TestKitConnectionError as e:
                _logger.debug("Error connecting to client: %r", e)
            else:
                _logger.info("Frame points (%d total): %r", len(frame_points), frame_points)
                if frame_points:
                    return frame_points
                if not return_nonempty:
                    return frame_points
            if time.monotonic() - started_at > wait_timeout_sec:
                raise TimeoutError(
                    f"Timed out ({wait_timeout_sec} seconds) waiting for {wait_message}")
            time.sleep(2)

    def wait_for_start(self):
        try:
            self._wait_for_time_frame_points(
                "client is ready (listening on http port)",
                _CLIENT_READY_TIMEOUT_SEC,
                )
        except TimeoutError as e:
            _logger.error(e)
            self._take_screenshot()
            raise

    def measure_connection_time(self, connect_timeout_sec):
        try:
            frame_points = self._wait_for_time_frame_points(
                "client is connected to server",
                connect_timeout_sec,
                return_nonempty=True,
                )
        except TimeoutError as e:
            _logger.error(e)
            self._take_screenshot()
            raise ClientServerConnectionError(
                f"Client did not connect to server in {connect_timeout_sec} seconds")
        connection_time_sec = frame_points[0] / 1000
        _logger.info("Client connected to the server in %.1f seconds", connection_time_sec)
        return timedelta(seconds=connection_time_sec)
