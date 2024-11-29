# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import shlex
import time
from contextlib import AbstractContextManager
from contextlib import ExitStack
from contextlib import closing
from contextlib import contextmanager
from datetime import datetime
from datetime import timezone
from pathlib import Path
from typing import Collection
from typing import Mapping
from typing import NamedTuple
from typing import cast
from urllib.error import URLError

from browser.chrome import ChromeConfiguration
from browser.chrome import ChromeDriverNotRunning
from browser.chrome import default_configuration
from browser.chrome import remote_chrome
from browser.webdriver import Browser
from directories import get_run_dir
from os_access import PosixAccess
from os_access import RemotePath
from os_access import copy_file
from os_access.screen_recorder.vlc import VLCScreenRecordingLinux
from vm.default_vm_pool import public_default_vm_pool
from vm.default_vm_pool import vm_types
from vm.vm import VM

_logger = logging.getLogger(__name__)


@contextmanager
def chrome_stand(allowed_hosts: Collection[str]) -> AbstractContextManager['_ChromeStand']:
    chrome_pool = _ChromeMachinePool(get_run_dir(), allowed_hosts)
    with chrome_pool.chrome_vm_allocation() as stand:
        yield stand


class _ChromeStand:

    def __init__(self, vm: VM, artifacts_dir: Path):
        self._vm = vm
        self._artifacts_dir = artifacts_dir
        self._logs = vm.os_access.path('/var/log/ft_chrome')
        self._logs.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def browser(
            self,
            configuration: ChromeConfiguration = default_configuration,
            ) -> AbstractContextManager[Browser]:
        os_access = cast(PosixAccess, self._vm.os_access)
        port_mapping = self._vm.vm_control.port_map()
        with ExitStack() as stack:
            stack.callback(self._copy_logs)
            x_server = stack.enter_context(_run_in_virtual_x_server(
                os_access,
                shlex.join([
                    './chromedriver',
                    '--allowed-ips=',
                    # See: https://chromedriver.chromium.org/logging
                    # See: https://developer.chrome.com/docs/chromedriver/logging
                    '--verbose',
                    f'--log-path={self._logs}/chromedriver.log',
                    ]),
                {'SSLKEYLOGFILE': f'{self._logs}/SSLKEYLOGFILE.txt'},
                self._logs,
                ))
            chrome_driver_url = f'http://{os_access.address}:{port_mapping["tcp"][9515]}'
            timeout_sec = 10
            started_at = time.monotonic()
            while True:
                try:
                    browser = stack.enter_context(
                        closing(remote_chrome(chrome_driver_url, configuration)))
                    break
                except ChromeDriverNotRunning as exc:
                    if time.monotonic() - started_at > timeout_sec:
                        raise RuntimeError("Timed out waiting for running Chrome Driver %r", exc)
                except OSError as err:
                    if not _is_connection_reset(err):
                        raise
                    if time.monotonic() - started_at > timeout_sec:
                        raise
                    logging.warning(
                        "Connection to %s is dropped. If ChromeDriver runs inside a VirtualBox VM. "
                        "Probably the VM is running but ChromeDriver is not",
                        chrome_driver_url)
                time.sleep(0.5)
            port = port_mapping["tcp"][12312]
            recorder = VLCScreenRecordingLinux(
                os_access, x_server.display, x_server.authority_file, port)
            recorder.start()
            try:
                try:
                    yield browser
                finally:
                    logs = browser.get_logs()
                    for log_type, log in logs.items():
                        path = self._artifacts_dir / f'chrome-{log_type}.log'
                        with open(path, 'w', encoding='utf8') as f:
                            _write_log_to_file(f, log)
            finally:
                recorder.stop_and_save(self._artifacts_dir)

    def vm(self) -> VM:
        return self._vm

    def _copy_logs(self):
        for log_file in self._logs.glob('*'):
            copy_file(log_file, self._artifacts_dir / log_file.name)


def _is_connection_reset(exception: OSError) -> bool:
    if isinstance(exception, URLError):
        exception = exception.reason
    return isinstance(exception, ConnectionResetError)


def _write_log_to_file(f, log):
    for entry in log:
        if not isinstance(entry, dict):
            f.write(str(entry))
        else:
            level = entry.pop('level', 'NO_LEVEL')
            f.write(level)
            f.write(' ')
            try:
                timestamp_ms = entry.pop('timestamp')
            except KeyError:
                timestamp_str = 'no_timestamp'
            else:
                try:
                    timestamp_sec = timestamp_ms / 1000
                    timestamp = datetime.fromtimestamp(timestamp_sec, timezone.utc)
                    timestamp_str = timestamp.isoformat(timespec='microseconds')
                except (ValueError, OSError):  # OSError if out of range
                    timestamp_str = str(timestamp_ms)
            f.write(timestamp_str)
            f.write(' ')
            message = entry.pop('message', '(no message)')
            if entry:
                f.write('extra=')
                json.dump(entry, f)
                f.write(' ')
            f.write(message)
        f.write('\n')


class _ChromeMachinePool:

    def __init__(
            self,
            artifacts_dir: Path,
            allowed_hosts: Collection[str],
            ):
        self._os_name = 'chrome'
        self._artifact_dir = artifacts_dir
        self._vm_pool = public_default_vm_pool(self._artifact_dir)
        self._allowed_hosts = allowed_hosts

    @contextmanager
    def chrome_vm_allocation(self) -> AbstractContextManager[_ChromeStand]:
        with ExitStack() as stack:
            vm = stack.enter_context(self._vm_pool.clean_vm(vm_types[self._os_name]))
            try:
                vm.ensure_started(self._artifact_dir)
                stack.enter_context(vm.os_access.traffic_capture_collector(self._artifact_dir))
                stack.enter_context(vm.os_access.prepared_one_shot_vm(self._artifact_dir))
                vm.os_access.networking.allow_hosts(self._allowed_hosts)
                yield _ChromeStand(vm, self._artifact_dir)
            except Exception:
                logging.exception("An exception happened in chrome allocation():")
                vm.vm_control.take_screenshot(self._artifact_dir / 'one_vm_exception.png')
                raise
            finally:
                vm.vm_control.copy_logs(self._artifact_dir)


class _VirtualDisplay(NamedTuple):
    display: int
    authority_file: str


@contextmanager
def _run_in_virtual_x_server(
        os_access: PosixAccess,
        command: str,
        env: Mapping[str, str],
        logs_dir: RemotePath,
        ) -> AbstractContextManager[_VirtualDisplay]:
    authority_file = '/root/.Xauthority'
    stdout_file = logs_dir / 'xserver_stdout.log'
    stderr_file = logs_dir / 'xserver_stderr.log'
    server_number = 99
    xvfb_command = [
        *[f'{k}={v}' for k, v in env.items()],
        'xvfb-run',
        f'--server-num={server_number}',
        f'--auth-file={authority_file}',
        f'--error-file={str(stderr_file)}',
        '--server-args=-screen 0 1920x1080x24 -noreset',
        ]
    command_string = shlex.join(xvfb_command) + ' ' + command + ' > ' + str(stdout_file)
    with os_access.shell.Popen(command_string, terminal=True) as run:
        timeout = 5
        started_at = time.monotonic()
        while True:
            if os_access.path(f'/tmp/.X11-unix/X{server_number}').exists():
                break
            if time.monotonic() - started_at > timeout:
                raise RuntimeError(f"Virtual X server has not started after {timeout} seconds")
        _logger.debug("Virtual X server started")
        try:
            yield _VirtualDisplay(display=server_number, authority_file=authority_file)
        finally:
            try:
                run.terminate()
            except OSError as e:
                if str(e) == 'Socket is closed':  # Raised from paramiko.channel. Not an error.
                    _logger.warning("Error terminating client run: %s", e)
                else:
                    raise
