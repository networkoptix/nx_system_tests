# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
# TODO: rename this module and class after package is renamed (VMS-15823 is done)

import logging
import re
import time
from contextlib import contextmanager
from contextlib import suppress
from threading import Thread
from typing import Collection
from typing import Generator
from typing import NamedTuple
from typing import Optional
from typing import Sequence
from typing import Union

from installation._base_installation import BaseInstallation
from installation._installer_supplier import InstallerSupplier
from os_access import OsAccess
from os_access import RemotePath
from os_access import Run
from os_access import WindowsAccess

_logger = logging.getLogger(__name__)


def install_vms_benchmark(os_access: OsAccess, installer_supplier: InstallerSupplier) -> 'VmsBenchmarkInstallation':
    installer = installer_supplier.upload_benchmark(os_access)
    installation = VmsBenchmarkInstallation(os_access)
    installation.install(installer)
    return installation


def _set_test_camera_streaming_events(test_camera_process: Run):
    buffer = bytearray()
    while True:
        [stdout, stderr] = test_camera_process.receive(timeout_sec=1)
        if stdout or stderr:
            _logger.debug(
                "Testcamera output:\n"
                "=== stdout ===\n%s%s"
                "=== stderr ===\n%s%s",
                stdout.decode(errors='backslashreplace') if stdout is not None else "",
                "(empty)" if not stdout else "\n(no newline)\n" if not stdout.endswith(b'\n') else "",
                stderr.decode(errors='backslashreplace') if stderr is not None else "",
                "(empty)" if not stderr else "\n(no newline)\n" if not stderr.endswith(b'\n') else "",
                )
        else:
            _logger.debug("Testcamera output: nothing")
        if test_camera_process.returncode is not None:
            _logger.warning(
                "Process terminated with returncode %d; stdout: %s; stderr: %s",
                test_camera_process.returncode, stdout, stderr)
            return
        if stdout is not None:
            buffer += stdout
        [*lines, buffer] = buffer.split(b'\r\n')
        for line in lines:
            if b'Start streaming' in line:
                _logger.info("Test camera: Streaming started")
            if b'All active streams closed' in line:
                _logger.info("Test camera: All active streams closed")
        time.sleep(1)


class TestCameraConfig(NamedTuple):

    hi_res_sample: RemotePath
    low_res_sample: Optional[RemotePath] = None
    name: Optional[str] = None


def _make_testcamera_arg_value(args: Sequence[Union[str, RemotePath, None]]) -> str:
    result = []
    for arg in args:
        result.append(str(arg)) if arg is not None else result.append('')
    return ','.join(result)


class TestCameraApp:

    def __init__(
            self,
            os_access: OsAccess,
            test_camera_binary: RemotePath,
            camera_configs: Collection[TestCameraConfig],
            camera_count: Optional[int] = None,
            ):
        self._os_access = os_access
        self._test_camera_binary = test_camera_binary
        self._camera_count = camera_count
        self._camera_configs = camera_configs
        self.discovery_port = 4983  # Non-default to avoid unexpected cameras.

    def _make_cameras_args(self):
        args_map = {
            'primary': [],
            'secondary': [],
            'names': [],
            }
        for config in self._camera_configs:
            args_map['primary'].append(config.hi_res_sample)
            args_map['secondary'].append(config.low_res_sample)
            args_map['names'].append(config.name)
        args = [f'files={_make_testcamera_arg_value(args_map["primary"])}']
        if any([file is not None for file in args_map['secondary']]):
            args.append(f'secondary-files={_make_testcamera_arg_value(args_map["secondary"])}')
        if any([name is not None for name in args_map['names']]):
            args.append(f'names={_make_testcamera_arg_value(args_map["names"])}')
        # Be aware that some parameters are not keys, they must be separated by ';',
        # not whitespace. There are also keys, that must be separated by whitespace.
        # Read testcamera help to get list of semicolon-separated parameters and keys.
        # The count arg is here because it's a part of ';'-separated parameters.
        if self._camera_count is not None:
            args.append(f'count={self._camera_count}')
        return ';'.join(args)

    @contextmanager
    def running(self):
        self._os_access.kill_all_by_name(self._test_camera_binary.name)
        args = [
            str(self._test_camera_binary),
            self._make_cameras_args(),
            f'--discovery-port={self.discovery_port}',
            '--local-interface=*',
            ]
        if self._camera_count is None:
            # One camera per each primary stream file. Currently, no tests use testcamera(-s) with
            # streams made by merging a sequence of files together.
            args.append('-S')
        if isinstance(self._os_access, WindowsAccess):
            run = self._os_access.winrm_shell().Popen(args)
        else:
            run = self._os_access.shell.Popen(args, terminal=True)
        events_thread = Thread(
            target=_set_test_camera_streaming_events,
            args=[run],
            name='test-camera',
            daemon=True,
            )
        events_thread.start()
        try:
            yield
        finally:
            run.terminate()
            run.close()
            events_thread.join(timeout=30)

    def running_address(self):
        return self._os_access.address

    def list_camera_configs(self):
        return [c for c in self._camera_configs]


class _RtspPerfStatistics(NamedTuple):
    bitrate_mbps: float
    active_sessions: int
    failed_sessions: int


class VmsBenchmarkInstallation(BaseInstallation):

    def __init__(self, os_access):
        dir = os_access.home() / 'vms_benchmark' / 'vms_benchmark'
        super().__init__(os_access, dir)
        tools_dir = self.dir / 'tools'
        self._test_camera_binary = tools_dir.joinpath('bin/testcamera').with_suffix(os_access.executable_suffix)
        self._rtsp_perf_binary = tools_dir.joinpath('bin/rtsp_perf').with_suffix(os_access.executable_suffix)

    def get_binary_path(self):
        return self.dir.joinpath('vms_benchmark').with_suffix(self.os_access.executable_suffix)

    def is_valid(self):
        return all([
            self._build_info_file.exists(),
            self.get_binary_path().exists(),
            self._test_camera_binary.exists(),
            self._rtsp_perf_binary.exists(),
            ])

    def uninstall_all(self):
        with suppress(FileNotFoundError):
            self.dir.parent.rmtree()

    def install(self, installer):
        self.os_access.unzip(installer, self.dir.parent)
        if not self.is_valid():
            raise RuntimeError(f"{self!r} is invalid when just installed")

    _RTSP_PERF_OUTPUT_REGEX = re.compile(
        r'Total bitrate (?P<bitrate>[\d.]+) MBit/s, working sessions '
        r'(?P<active_sessions>\d+), failed (?P<failures>\d+)')

    def _start_rtsp_perf(
            self,
            rtsp_urls: Collection[str],
            username: str,
            password: str,
            live_percent: int,
            process_name: str,
            ) -> Generator[_RtspPerfStatistics, None, None]:
        rtsp_urls_file = self.dir / f'url-list-{process_name}.txt'
        rtsp_urls_file.write_text('\n'.join(rtsp_urls))
        args = [
            str(self._rtsp_perf_binary),
            f'--live_percent={live_percent}',
            f'--count={len(rtsp_urls)}',
            f'--user={username}',
            f'--password={password}',
            '--interval=100',  # Use fixed restart interval
            '--archive-position=0',  # It is random by default, which is not good for tests.
            f'--url-file={rtsp_urls_file}',
            ]
        if self.newer_than('vms_5.0'):
            args.append('--digest')
        if isinstance(self.os_access, WindowsAccess):
            run = self.os_access.winrm_shell().Popen(args)
        else:
            run = self.os_access.shell.Popen(args, terminal=True)
        proper_output_received_at = time.monotonic()
        silence_sec = 30
        buffer = bytearray()
        rtsp_info = []
        while True:
            [stdout, _] = run.receive(timeout_sec=2)
            if stdout is not None:
                # rtsp_perf uses \r\n as line separator and puts arbitrary \r inside lines.
                buffer += stdout.replace(b'\r', b'')
            [*lines, buffer] = buffer.split(b'\n')
            for line in lines:
                decoded_line = line.decode('ascii')
                _logger.debug('rtsp_perf output: %s', decoded_line)
                match = self._RTSP_PERF_OUTPUT_REGEX.search(decoded_line)
                if match is None:
                    rtsp_info.append(decoded_line)
                    continue
                yield _RtspPerfStatistics(
                    bitrate_mbps=float(match.group('bitrate')),
                    active_sessions=int(match.group('active_sessions')),
                    failed_sessions=int(match.group('failures')),
                    )
                proper_output_received_at = time.monotonic()
            if run.returncode is not None:
                output = '\n'.join(rtsp_info)
                raise RuntimeError(
                    f"{process_name} ended prematurely; return code {run.returncode}; "
                    f"output: {output}")
            if time.monotonic() - proper_output_received_at > silence_sec:
                output = '\n'.join(rtsp_info)
                raise RuntimeError(
                    f"rtsp_perf: Failed to get expected output in {silence_sec} seconds. "
                    f"Output: {output}")

    def start_rtsp_perf_live(self, rtsp_urls: Collection[str], username: str, password: str):
        return self._start_rtsp_perf(
            rtsp_urls, username, password, live_percent=100, process_name='rtsp_perf-live')

    def start_rtsp_perf_archive(self, rtsp_urls: Collection[str], username: str, password: str):
        return self._start_rtsp_perf(
            rtsp_urls, username, password, live_percent=0, process_name='rtsp_perf-archive')

    def stop_rtsp_perf(self):
        self.os_access.kill_all_by_name(self._rtsp_perf_binary.name)

    def single_testcamera(
            self,
            camera_config: TestCameraConfig,
            ) -> TestCameraApp:
        return TestCameraApp(
            os_access=self.os_access,
            test_camera_binary=self._test_camera_binary,
            camera_configs=[camera_config],
            )

    def similar_testcameras(
            self,
            camera_config: TestCameraConfig,
            camera_count: int,
            ) -> TestCameraApp:
        return TestCameraApp(
            os_access=self.os_access,
            test_camera_binary=self._test_camera_binary,
            camera_configs=[camera_config],
            camera_count=camera_count,
            )

    def different_testcameras(
            self,
            camera_configs: Collection[TestCameraConfig],
            ) -> TestCameraApp:
        return TestCameraApp(
            os_access=self.os_access,
            test_camera_binary=self._test_camera_binary,
            camera_configs=camera_configs,
            )
