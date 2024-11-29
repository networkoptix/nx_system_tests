# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from collections import Counter
from contextlib import ExitStack
from ipaddress import IPv4Network
from ssl import SSLError
from typing import Any
from typing import Mapping
from typing import cast

from directories import get_run_dir
from installation import Mediaserver
from long_tests._common import get_build_info
from long_tests._common import get_installers_url
from long_tests._common import license_server_running
from long_tests._mediaserver_events import _EventQueue
from long_tests._run_single_test import ComparisonTest
from long_tests._run_single_test import run_test
from long_tests._run_single_test import select_comparison_test
from long_tests._vm_pool import BenchmarkStand
from long_tests._vm_pool import VMPool
from long_tests._vm_pool import make_changed_vm_configuration
from mediaserver_api import EventType
from mediaserver_api import MediaserverApi
from mediaserver_api import MediaserverApiReadTimeout
from mediaserver_scenarios.provisioned_mediaservers import OneMediaserverStand
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras_hi_low
from os_access import WindowsAccess
from vm.default_vm_pool import vm_types
from vm.networks import setup_flat_network
from vm.vm import VM


@ComparisonTest('comparison_maximum_recorded_cameras')
def test_ubuntu22_3600s(exit_stack: ExitStack) -> Mapping[str, Any]:
    cameras_count = 100  # The value has been found experimentally.
    _logger.info(
        "Parameters: cameras_count=%d, other parameters: %s",
        cameras_count, sys.argv[1:])
    return _test_maximum_recoding_cameras(
        exit_stack=exit_stack,
        cameras_count=cameras_count,
        duration=3600,
        os_name='ubuntu22',
        )


@ComparisonTest('comparison_maximum_recorded_cameras')
def test_win11_3600s(exit_stack: ExitStack) -> Mapping[str, Any]:
    cameras_count = 100  # The value has been found experimentally.
    _logger.info(
        "Parameters: cameras_count=%d, other parameters: %s",
        cameras_count, sys.argv[1:])
    return _test_maximum_recoding_cameras(
        exit_stack=exit_stack,
        cameras_count=cameras_count,
        duration=3600,
        os_name='win11',
        )


def _test_maximum_recoding_cameras(
        exit_stack: ExitStack,
        cameras_count: int,
        duration: int,
        os_name: str,
        ) -> Mapping[str, Any]:
    # See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/2945482753
    logging.getLogger('mediaserver_api._mediaserver.http_resp.large').setLevel(logging.INFO)  # Too many logs
    artifacts_dir = get_run_dir()
    if os_name.startswith('ubuntu'):
        vm_type = make_changed_vm_configuration(vm_types[os_name], 5120, 4)
    else:
        vm_type = make_changed_vm_configuration(vm_types[os_name], 8192, 4)
    vm_pool = VMPool(artifacts_dir, get_installers_url())
    mediaserver_stand: OneMediaserverStand = exit_stack.enter_context(
        vm_pool.mediaserver_stand(vm_type))
    if isinstance(mediaserver_stand.os_access(), WindowsAccess):
        _reset_windows_license_status(mediaserver_stand.vm())
    benchmark_stand: BenchmarkStand = exit_stack.enter_context(vm_pool.benchmark_stand())
    [[_, ip_benchmark], _] = setup_flat_network(
        (mediaserver_stand.vm(), benchmark_stand.vm()), IPv4Network('10.254.254.0/28'))
    _logger.info("Add a storage with limited bandwidth to the Mediaserver and set it up as the default storage")
    # The storage with limited bandwidth can only be added when the VM is powered off.
    mediaserver_stand.vm().vm_control.shutdown()
    mediaserver_stand.vm().vm_control.add_disk_limited('USB', 40 * 1024, 60)
    mediaserver_stand.vm().vm_control.power_on()
    mediaserver_stand.vm().ensure_started(artifacts_dir)
    storage_path = mediaserver_stand.vm().os_access.mount_disk('U')
    [default_storage] = mediaserver_stand.api().list_storages(
        mediaserver_stand.mediaserver().default_archive().storage_root_path())
    mediaserver_stand.api().add_storage_encryption_key('WellKnownPassword1')
    mediaserver_stand.api().set_system_settings({"storageEncryption": True})
    mediaserver_stand.api().disable_storage(default_storage.id)
    [_, storage] = mediaserver_stand.api().set_up_new_storage(storage_path)
    exit_stack.enter_context(license_server_running(mediaserver_stand.mediaserver()))
    exit_stack.enter_context(similar_playing_testcameras_hi_low(
        'samples/hi.ts', 'samples/lo.ts', cameras_count, benchmark_stand.installation()))
    _logger.info("Start and enable recording for %d cameras", cameras_count)
    cameras = mediaserver_stand.api().add_test_cameras(0, cameras_count, address=ip_benchmark)
    mediaserver_stand.api().start_recording(*[camera.id for camera in cameras], fps=30)
    _logger.info("Fill up free space")
    storages = mediaserver_stand.api().list_storages(storage.path)
    dummy_file_size = storages[0].free_space - storages[0].reserved_space - 5 * 1024**3
    mediaserver_stand.os_access().create_file(storage_path / 'dummy', dummy_file_size)
    started_at = time.monotonic()
    while True:
        storages = mediaserver_stand.api().list_storages(storage.path)
        space_for_fill = storages[0].free_space - storages[0].reserved_space
        if space_for_fill <= storages[0].reserved_space * 1.05:
            break
        else:
            _logger.info(
                "Waiting for fill free space. Available space: %.2f MB",
                space_for_fill / 1024 / 1024)
            if time.monotonic() - started_at > 120:
                raise RuntimeError("Filling up the free space took too long")
            time.sleep(30)
    _logger.info("Wait until all cameras are in Recording status")
    started_at = time.monotonic()
    while True:
        if _count_recording_cameras(mediaserver_stand.api()) == cameras_count:
            break
        if time.monotonic() - started_at > 120:
            raise RuntimeError("Test failed - not all cameras in the status Recording")
        time.sleep(10)
    time.sleep(300)
    assert _count_recording_cameras(mediaserver_stand.api()) > 0
    if mediaserver_stand.mediaserver().older_than('vms_6.1'):
        event_name = EventType.STORAGE_FAILURE
    else:
        event_name = 'nx.events.storageIssue'
    event_queue = _EventQueue(mediaserver_stand.api(), [event_name])
    event_queue.clear()
    _logger.info("Part 1. Reduce the number of recording cameras until storage errors do not appear")
    camera_num = cameras_count
    started_at = time.monotonic()
    while True:
        _logger.info(
            "RAM usage by mediaserver: %.0f MB, total usage: %.0f MB",
            *_get_ram_usage_mbytes(mediaserver_stand.mediaserver()),
            )
        if event_queue.get_last_events():
            _logger.info("Found storage failure events with %d cameras", camera_num)
            camera_num -= 1
            if camera_num <= 0:
                RuntimeError("Test failed - no cameras left")
            mediaserver_stand.api().stop_recording(cameras[camera_num].id)
            _logger.info("Stop recording for camera %d", camera_num)
            started_at = time.monotonic()
        else:
            _logger.info("%.0f minutes without errors", (time.monotonic() - started_at) / 60)
        assert _count_recording_cameras(mediaserver_stand.api()) > 0
        if time.monotonic() - started_at > duration:
            break
        time.sleep(60)
    cameras_without_errors_1 = camera_num
    _logger.info("No storage failure events with %d cameras", cameras_without_errors_1)
    _logger.info("Disable recording for all cameras")
    mediaserver_stand.api().setup_recording(*[camera.id for camera in cameras], enable_recording=False)
    started_at = time.monotonic()
    while True:
        if _count_recording_cameras(mediaserver_stand.api()) == 0:
            break
        if time.monotonic() - started_at > 60:
            raise RuntimeError("Test failed - not all cameras have stopped recording")
        time.sleep(5)
    _logger.info("Part 2. Increase the number of recording cameras until storage errors appear")
    cameras_count = int(cameras_without_errors_1 * 0.9)
    mediaserver_stand.api().start_recording(*[camera.id for camera in cameras[:cameras_count]], fps=30)
    time.sleep(300)
    assert _count_recording_cameras(mediaserver_stand.api()) > 0
    event_queue.clear()
    camera_num = cameras_count
    started_at = time.monotonic()
    while True:
        _logger.info(
            "RAM usage by mediaserver: %.0f MB, total usage: %.0f MB",
            *_get_ram_usage_mbytes(mediaserver_stand.mediaserver()),
            )
        if event_queue.get_last_events():
            _logger.info("Found storage failure events with %d cameras", camera_num)
            camera_num -= 1
            break
        else:
            _logger.info("%.0f minutes without errors", (time.monotonic() - started_at) / 60)
            camera_num += 1
            mediaserver_stand.api().start_recording(
                cameras[camera_num].id, single_request=True, fps=30)
            _logger.info("Start recording for camera %d", camera_num)
        assert _count_recording_cameras(mediaserver_stand.api()) > 0
        time.sleep(600)
    cameras_without_errors_2 = camera_num
    _logger.info("Test finished with score: %d, %d", cameras_without_errors_1, cameras_without_errors_2)
    mediaserver_ram_usage, total_ram_usage = _get_ram_usage_mbytes(mediaserver_stand.mediaserver())
    result = {
        'test_duration_sec': duration,
        'stand': {
            'CPU': vm_type._cpu_count,
            'RAM': vm_type._ram_mb,
            },
        'OS': os_name,
        'ram_mediaserver_usage_mb': mediaserver_ram_usage,
        'ram_total_usage_mb': total_ram_usage,
        'pass1': cameras_without_errors_1,
        'pass2': cameras_without_errors_2,
        **get_build_info(mediaserver_stand.mediaserver()),
        }
    mediaserver_stand.api().setup_recording(*[camera.id for camera in cameras], enable_recording=False)
    _wait_while_recording_stopped(mediaserver_stand.api())
    return result


def _get_ram_usage_mbytes(mediaserver: Mediaserver) -> tuple[int, int]:
    vms_pid = mediaserver.service.status().pid
    if vms_pid <= 0:
        return 0, 0
    ram_usage = mediaserver.os_access.get_ram_usage(vms_pid)
    process_usage = int(ram_usage.process_usage_bytes / 1024 / 1024)
    total_usage = int(ram_usage.total_usage_bytes / 1024 / 1024)
    return process_usage, total_usage


def _count_recording_cameras(api: MediaserverApi) -> int:
    try:
        statuses = Counter([c.status for c in api.list_cameras()])
    except (SSLError, MediaserverApiReadTimeout):
        # These errors can be seen on Windows 11, presumable because of high load.
        statuses = Counter([c.status for c in api.list_cameras()])
    _logger.info('Cameras statuses: %s', statuses)
    return statuses.get('Recording', 0)


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


def _reset_windows_license_status(vm: VM):
    # The Windows trial period is rearmed during snapshot building, but sometimes Windows still expires.
    # There is a suspicion that this issue occurs when more than one VM with the same copy of
    # Windows is running on the same physical server.
    os_access = cast(WindowsAccess, vm.os_access)
    # Setting SkipRearm=1 resets the Windows licensing state.
    # See: https://learn.microsoft.com/en-us/windows-hardware/customize/desktop/unattend/microsoft-windows-security-spp-skiprearm
    os_access.registry.set_dword(
        r'HKLM\SOFTWARE\Microsoft\Windows NT\CurrentVersion\SoftwareProtectionPlatform', 'SkipRearm', 1)
    # Rearm the Windows evaluation license.
    os_access.run(['cscript', '//B', r'%windir%\system32\slmgr.vbs', '/rearm'])
    # A reboot is needed, but it will occur later in the test.


if __name__ == '__main__':
    _logger = logging.getLogger(__name__)
    exit(run_test(select_comparison_test(sys.argv[1:], [
        test_ubuntu22_3600s,
        test_win11_3600s,
        ])))
