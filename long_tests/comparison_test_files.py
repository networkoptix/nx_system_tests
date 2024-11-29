# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import sys
import time
from collections import Counter
from contextlib import ExitStack
from ipaddress import IPv4Network
from typing import Any
from typing import Mapping
from typing import NamedTuple
from typing import cast

from directories import get_run_dir
from installation import Mediaserver
from installation import MediaserverHangingError
from installation import MediaserverMetrics
from long_tests._common import get_build_info
from long_tests._common import get_installers_url
from long_tests._common import license_server_running
from long_tests._run_single_test import ComparisonTest
from long_tests._run_single_test import run_test
from long_tests._run_single_test import select_comparison_test
from long_tests._vm_pool import BenchmarkStand
from long_tests._vm_pool import VMPool
from long_tests._vm_pool import make_changed_vm_configuration
from long_tests.strace import strace
from mediaserver_api import MediaserverApi
from mediaserver_api import MotionParameters
from mediaserver_api import MotionType
from mediaserver_scenarios.provisioned_mediaservers import OneMediaserverStand
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras_hi_low
from os_access import PosixAccess
from vm.default_vm_pool import vm_types
from vm.networks import setup_flat_network


@ComparisonTest('comparison_files')
def test_1800s(exit_stack: ExitStack) -> Mapping[str, Any]:
    cameras_count = 16
    _logger.info(
        'Parameters: cameras_count=%d, other parameters: %s', cameras_count, sys.argv[1:])
    return _comparison_test_files(
        exit_stack=exit_stack,
        cameras_count=cameras_count,
        duration_sec=1800,
        with_object_detection=False,
        )


@ComparisonTest('comparison_files_with_object_detection')
def test_1800s_with_object_detection(exit_stack: ExitStack) -> Mapping[str, Any]:
    cameras_count = 16
    _logger.info(
        'Parameters: cameras_count=%d, other parameters: %s', cameras_count, sys.argv[1:])
    return _comparison_test_files(
        exit_stack=exit_stack,
        cameras_count=cameras_count,
        duration_sec=1800,
        with_object_detection=True,
        )


def _comparison_test_files(
        exit_stack: ExitStack,
        cameras_count: int,
        duration_sec: int,
        with_object_detection: bool,
        ) -> Mapping[str, Any]:
    # See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/2864185358
    artifacts_dir = get_run_dir()
    _logger.info('Create an infrastructure')
    vm_pool = VMPool(
        artifacts_dir,
        get_installers_url(),
        )
    vm_type = make_changed_vm_configuration(vm_types['ubuntu22'], 2048, 2)
    benchmark_stand: BenchmarkStand = exit_stack.enter_context(vm_pool.benchmark_stand())
    plugins = ['stub'] if with_object_detection else None
    mediaserver_stand: OneMediaserverStand = exit_stack.enter_context(
        vm_pool.mediaserver_stand(vm_type, plugins=plugins, full_logs=True))
    exit_stack.enter_context(license_server_running(mediaserver_stand.mediaserver()))
    [[_, ip_benchmark], _] = setup_flat_network(
        (mediaserver_stand.vm(), benchmark_stand.vm()), IPv4Network('10.254.254.0/28'))
    #
    _logger.info('Add and setup %s cameras', cameras_count)
    exit_stack.enter_context(similar_playing_testcameras_hi_low(
        'samples/hi.ts', 'samples/lo.ts', cameras_count, benchmark_stand.installation()))
    cameras = mediaserver_stand.api().add_test_cameras(0, cameras_count, address=ip_benchmark)
    cameras_ids = [camera.id for camera in cameras]
    if with_object_detection:
        engine_collection = mediaserver_stand.api().get_analytics_engine_collection()
        engine_object_detection = engine_collection.get_stub('Object Detection')
        for camera in cameras:
            mediaserver_stand.api().enable_device_agent(engine_object_detection, camera.id)
        mediaserver_stand.api().set_motion_type_for_cameras(cameras_ids, MotionType.DEFAULT)
    mediaserver_stand.api().setup_recording(
        *cameras_ids,
        enable_recording=True,
        motion_params=MotionParameters('9,0,0,44,32', 0, 20),
        fps=30,
        )
    _logger.info('Start test. Wait for %d seconds', duration_sec)
    pid = mediaserver_stand.os_access().get_pid_by_name('mediaserver')
    posix_access = cast(PosixAccess, mediaserver_stand.os_access())
    build_info = get_build_info(mediaserver_stand.mediaserver())
    mediaserver_metrics = MediaserverMetrics(mediaserver_stand.mediaserver())
    with strace(posix_access, pid) as strace_log:
        time.sleep(duration_sec)
        mediaserver_stand.api().setup_recording(*cameras_ids, enable_recording=False)
        _wait_while_recording_stopped(mediaserver_stand.api())
        _stop_mediaserver(mediaserver_stand.mediaserver())
    os_metrics = mediaserver_metrics.get_os_metrics()
    log_filtered = strace_log.with_suffix('.filtered')
    command = f"cat {str(strace_log)} | grep '</opt/networkoptix' > {str(log_filtered)}"
    mediaserver_stand.os_access().run(command)
    log = log_filtered.read_text()
    (artifacts_dir / strace_log.name).write_text(log)
    events = Counter([parse_line(line) for line in log.splitlines()])
    records = []
    for event, count in events.items():
        if '(deleted)' in event.path:
            continue
        records.append({**event._asdict(), 'count': count})
    result = {
        'test_duration_sec': duration_sec,
        'stand': {
            'CPU': vm_type._cpu_count,
            'RAM': vm_type._ram_mb,
            },
        'OS': vm_type._name,
        'measures': records,
        **build_info,
        'metrics': {
            **os_metrics,
            },
        }
    return result


def parse_line(line: str) -> 'Event':
    pattern = re.compile(r'\d+\s+(\w+)\(\d+<(.+?)>.*$')
    for match in pattern.finditer(line):
        if 'write' in match.group(1):
            operation = 'write'
        elif 'read' in match.group(1):
            operation = 'read'
        else:
            operation = match.group(1)
        return Event(operation=operation, path=match.group(2))


class Event(NamedTuple):
    operation: str
    path: str


def _wait_while_recording_stopped(api: MediaserverApi):
    finished_at = time.monotonic() + 30
    while True:
        statuses = Counter([c.status for c in api.list_cameras()])
        _logger.debug('Camera statuses: %s', statuses)
        if 'Recording' not in statuses:
            return
        if time.monotonic() > finished_at:
            raise RuntimeError('Recording is not stopped')
        time.sleep(1)


def _stop_mediaserver(mediaserver: Mediaserver):
    try:
        mediaserver.stop()
    except MediaserverHangingError:
        _logger.warning('Failed to stop mediaserver. Try again.')
        time.sleep(10)
        mediaserver.stop(already_stopped_ok=True)


if __name__ == '__main__':
    _logger = logging.getLogger(__name__)
    exit(run_test(select_comparison_test(sys.argv[1:], [
        test_1800s,
        test_1800s_with_object_detection,
        ])))
