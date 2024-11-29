# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from collections import Counter
from contextlib import ExitStack
from ipaddress import IPv4Network
from typing import Any
from typing import Mapping

from directories import get_run_dir
from installation import OsCollectingMetrics
from long_tests._common import get_build_info
from long_tests._common import get_installers_url
from long_tests._common import license_server_running
from long_tests._run_single_test import ComparisonTest
from long_tests._run_single_test import run_test
from long_tests._run_single_test import select_comparison_test
from long_tests._vm_pool import BenchmarkStand
from long_tests._vm_pool import VMPool
from long_tests._vm_pool import make_changed_vm_configuration
from mediaserver_scenarios.provisioned_mediaservers import OneMediaserverStand
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras_hi_low
from vm.default_vm_pool import vm_types
from vm.networks import setup_flat_network


@ComparisonTest('comparison_ram_cpu')
def test_ubuntu22_1800s(exit_stack: ExitStack) -> Mapping[str, Any]:
    cameras_count = 80
    _logger.info(
        'Parameters: cameras_count=%d, other parameters: %s', cameras_count, sys.argv[1:])
    return _comparison_test_cpu_ram_usage(
        exit_stack=exit_stack,
        cameras_count=cameras_count,
        duration_sec=1800,
        os_name='ubuntu22',
        )


@ComparisonTest('comparison_ram_cpu')
def test_win11_1800s(exit_stack: ExitStack) -> Mapping[str, Any]:
    cameras_count = 80
    _logger.info(
        'Parameters: cameras_count=%d, other parameters: %s', cameras_count, sys.argv[1:])
    return _comparison_test_cpu_ram_usage(
        exit_stack=exit_stack,
        cameras_count=cameras_count,
        duration_sec=1800,
        os_name='win11',
        )


def _comparison_test_cpu_ram_usage(
        exit_stack: ExitStack,
        cameras_count: int,
        duration_sec: int,
        os_name: str,
        ) -> Mapping[str, Any]:
    # See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/2945286198
    # Create an infrastructure
    if os_name.startswith('ubuntu'):
        vm_type = make_changed_vm_configuration(vm_types[os_name], 5120, 2)
    else:
        vm_type = vm_types[os_name]
    vm_pool = VMPool(
        get_run_dir(),
        get_installers_url(),
        )
    benchmark_stand: BenchmarkStand = exit_stack.enter_context(vm_pool.benchmark_stand())
    mediaserver_stand: OneMediaserverStand = exit_stack.enter_context(
        vm_pool.mediaserver_stand(vm_type))
    [[_, ip_benchmark], _] = setup_flat_network(
        (mediaserver_stand.vm(), benchmark_stand.vm()), IPv4Network('10.254.254.0/28'))
    exit_stack.enter_context(license_server_running(mediaserver_stand.mediaserver()))
    # Add a storage to mediaserver
    mediaserver_stand.vm().vm_control.add_disk('SATA', 40 * 1024)
    storage_path = mediaserver_stand.vm().os_access.mount_disk('U')
    [default_storage] = mediaserver_stand.api().list_storages(
        mediaserver_stand.mediaserver().default_archive().storage_root_path())
    mediaserver_stand.api().add_storage_encryption_key('WellKnownPassword1')
    mediaserver_stand.api().set_system_settings({"storageEncryption": True})
    mediaserver_stand.api().disable_storage(default_storage.id)
    [_, storage] = mediaserver_stand.api().set_up_new_storage(storage_path)
    #
    _logger.info('Start and enable recording for %s cameras', cameras_count)
    exit_stack.enter_context(similar_playing_testcameras_hi_low(
        'samples/hi.ts', 'samples/lo.ts', cameras_count, benchmark_stand.installation()))
    cameras = mediaserver_stand.api().add_test_cameras(
        0, cameras_count, address=ip_benchmark)
    mediaserver_stand.api().start_recording(*[camera.id for camera in cameras], fps=30)
    time.sleep(30)
    #
    _logger.info('Fill free space')
    storages = mediaserver_stand.api().list_storages(storage.path)
    dummy_file_size = storages[0].free_space - storages[0].reserved_space - 5 * 1024**2
    mediaserver_stand.os_access().create_file(storage_path / 'dummy', dummy_file_size)
    starting_at = time.monotonic()
    while True:
        storages = mediaserver_stand.api().list_storages(storage.path)
        space_for_fill = storages[0].free_space - storages[0].reserved_space
        if space_for_fill <= storages[0].reserved_space * 1.05:
            break
        else:
            _logger.info(
                'Waiting for fill free space. Available space: %.2f Mb',
                space_for_fill / 1024 / 1024)
            if time.monotonic() - starting_at > 120:
                raise RuntimeError('Test failed - filling free space take too long time')
            time.sleep(30)
    _logger.info('Wait for all cameras to be in the status Recording')
    time.sleep(30)
    starting_at = time.monotonic()
    while True:
        statuses = Counter([c.status for c in mediaserver_stand.api().list_cameras()])
        _logger.info('Cameras statuses: %s', statuses)
        if statuses.get('Recording', 0) == cameras_count:
            break
        if time.monotonic() - starting_at > 120:
            raise RuntimeError('Test failed - not all cameras in the status Recording')
        time.sleep(10)
    vms_pid = mediaserver_stand.mediaserver().service.status().pid
    if vms_pid <= 0:
        raise RuntimeError('Cannot get mediaserver PID')
    cpu_time = mediaserver_stand.os_access().get_cpu_time_process(vms_pid)
    _logger.info("Waiting for %s seconds", duration_sec)
    os_metrics = OsCollectingMetrics(mediaserver_stand.os_access())
    time.sleep(duration_sec)
    cpu_time = mediaserver_stand.os_access().get_cpu_time_process(vms_pid) - cpu_time
    ram_usage = mediaserver_stand.os_access().get_ram_usage(vms_pid)
    current_os_metrics = os_metrics.get_current()
    result = {
        'test_duration_sec': duration_sec,
        'stand': {
            'CPU': vm_type._cpu_count,
            'RAM': vm_type._ram_mb,
            },
        'OS': os_name,
        'cpu_total_usage': current_os_metrics['cpu_usage'],
        'cpu_mediaserver_usage': cpu_time / duration_sec / vm_type._cpu_count,
        'ram_total_usage_mb': ram_usage.total_usage_bytes / 1024 / 1024,
        'ram_mediaserver_usage_mb': ram_usage.process_usage_bytes / 1024 / 1024,
        **get_build_info(mediaserver_stand.mediaserver()),
        }
    return result


if __name__ == '__main__':
    _logger = logging.getLogger(__name__)
    exit(run_test(select_comparison_test(sys.argv[1:], [
        test_ubuntu22_1800s,
        test_win11_1800s,
        ])))
