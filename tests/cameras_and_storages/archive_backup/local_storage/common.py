# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import math
import time
from collections import Counter
from itertools import chain
from typing import Iterable
from uuid import UUID

from doubles.video.ffprobe import ffprobe_get_video_stream
from installation import Mediaserver
from installation import MediaserverArchive
from mediaserver_api import CameraStatus
from mediaserver_api import MediaserverApi
from mediaserver_api import Storage
from mediaserver_api import TimePeriod
from os_access import OsAccess
from os_access import RemotePath
from vm.hypervisor import Vm

_logger = logging.getLogger(__name__)


def add_backup_storage(server: Mediaserver, vm_control: Vm, letter: str, size_mb: int) -> Storage:
    path = _add_disk(server.os_access, vm_control, letter, size_mb)
    _, storage = server.api.set_up_new_storage(path, is_backup=True)
    return storage


def add_main_storage(server: Mediaserver, vm_control: Vm, letter: str, size_mb: int) -> Storage:
    path = _add_disk(server.os_access, vm_control, letter, size_mb)
    _, storage = server.api.set_up_new_storage(path, is_backup=False)
    return storage


def _add_disk(os_access: OsAccess, vm_control: Vm, letter: str, size_mb: int) -> RemotePath:
    vm_control.add_disk('sata', size_mb)
    return os_access.mount_disk(letter)


def compare_streams_properties(
        main_stream,
        backup_stream,
        bitrate_kbps_rel=0.01,
        backup_fps_rel=0.01):
    different_fields = {}
    main_bitrate_kbps = main_stream['bitrate_kbps']
    backup_bitrate_kbps = backup_stream['bitrate_kbps']
    if not math.isclose(backup_bitrate_kbps, main_bitrate_kbps, rel_tol=bitrate_kbps_rel):
        different_fields['bitrate_kbps'] = (
            f"main={main_bitrate_kbps}; backup={backup_bitrate_kbps}")
    main_duration_sec = main_stream['duration_sec']
    backup_duration_sec = backup_stream['duration_sec']
    if not math.isclose(backup_duration_sec, main_duration_sec, abs_tol=2.):
        different_fields['duration_sec'] = (
            f"main={main_duration_sec}; backup={backup_duration_sec}")
    main_fps = main_stream['fps']
    backup_fps = backup_stream['fps']
    if not math.isclose(backup_fps, main_fps, rel_tol=backup_fps_rel):
        different_fields['fps'] = f"main={main_fps}; backup={backup_fps}"
    main_codec = main_stream['codec']
    backup_codec = backup_stream['codec']
    if backup_codec != main_codec:
        different_fields['codec'] = f"main={main_codec}; backup={backup_codec}"
    main_resolution = main_stream['resolution']
    backup_resolution = backup_stream['resolution']
    if main_resolution != backup_resolution:
        different_fields['resolution'] = f"main={main_resolution}; backup={backup_resolution}"
    return different_fields


def backup_archive_size_is_enough(archive: MediaserverArchive, camera_physical_id: str, enough_size: int):
    return archive.camera_archive(camera_physical_id).size_bytes() >= enough_size


def get_video_properties(stream_url: str):
    stream = ffprobe_get_video_stream(stream_url)
    while True:
        try:
            next(stream)
        except StopIteration as e:
            return e.value


def wait_before_expected_backup_time(
        api, camera_id, backup_archive: MediaserverArchive, expected_backup_start_timestamp):
    _logger.info("Wait before expected backup start time")
    while True:
        current_timestamp = api.get_datetime().timestamp()
        actual_state = api.get_actual_backup_state(camera_id)
        if backup_archive.has_mkv_files():
            raise RuntimeError(
                "Backup started "
                f"{expected_backup_start_timestamp - current_timestamp} "
                "seconds earlier than expected")
        if actual_state.position != (0, 0):
            raise RuntimeError(
                "Backup state changed "
                f"{expected_backup_start_timestamp - current_timestamp} "
                "seconds earlier than expected "
                f": (0, 0) != {actual_state.position}")
        if (expected_backup_start_timestamp - current_timestamp) <= 1.5:
            break
        time.sleep(0.1)


# TODO: Got to be a method of MediaserverArchive
def wait_for_backup_started(api, camera_id, backup_archive: MediaserverArchive):
    timeout_sec = 30
    started_at = time.monotonic()
    _logger.info("Wait until backup started")
    while True:
        if backup_archive.has_mkv_files():
            break
        if time.monotonic() - started_at > timeout_sec:
            raise RuntimeError("Waiting for backup started is timed out")
        time.sleep(0.1)
    _logger.info("Wait until backup state updated")
    while True:
        actual_state = api.get_actual_backup_state(camera_id)
        if actual_state.position != (0, 0):
            return
        if time.monotonic() - started_at > timeout_sec:
            raise RuntimeError("Waiting for backup state updated is timed out")
        time.sleep(0.1)


def bookmark_is_backed_up(bookmark, backed_up_periods) -> bool:
    bookmark_start_timestamp = bookmark.start_time_ms / 1000
    bookmark_end_timestamp = bookmark_start_timestamp + bookmark.duration_ms / 1000
    for period in backed_up_periods:
        if bookmark_start_timestamp < period.start.timestamp():
            continue
        period_end_timestamp = period.start.timestamp() + period.duration_sec
        if bookmark_end_timestamp > period_end_timestamp:
            continue
        return True
    return False


def record_different_archive_types(api, camera_id, high_camera_server, low_camera_server):
    low_camera_server.video_source.stop_motion()
    high_camera_server.video_source.stop_motion()
    engine_collection = api.get_analytics_engine_collection()
    sample_engine = engine_collection.get_by_exact_name('Sample')
    with low_camera_server.async_serve():
        with high_camera_server.async_serve():
            api.start_recording(camera_id)
            wait_until_cameras_in_status(api, {camera_id}, CameraStatus.RECORDING)
            api.enable_device_agent(sample_engine, camera_id)
            time.sleep(5)
            api.disable_device_agents(camera_id)
            time.sleep(10)
            low_camera_server.video_source.start_motion()
            high_camera_server.video_source.start_motion()
            time.sleep(2)
            low_camera_server.video_source.stop_motion()
            high_camera_server.video_source.stop_motion()
            time.sleep(8)
            first_bookmark_started_at = int(api.get_datetime().timestamp() * 1000)
            time.sleep(6)
            api.enable_device_agent(sample_engine, camera_id)
            time.sleep(5)
            api.disable_device_agents(camera_id)
            time.sleep(10)
            low_camera_server.video_source.start_motion()
            high_camera_server.video_source.start_motion()
            time.sleep(2)
            low_camera_server.video_source.stop_motion()
            high_camera_server.video_source.stop_motion()
            time.sleep(8)
            second_bookmark_started_at = int(api.get_datetime().timestamp() * 1000)
            time.sleep(6)
            api.stop_recording(camera_id)
            wait_until_cameras_in_status(api, {camera_id}, CameraStatus.ONLINE)
    analytics_periods = api.list_analytics_periods(camera_id)
    motion_periods = api.list_motion_periods(camera_id)
    bookmark_duration_ms = 1000
    bookmark_periods = [
        TimePeriod(first_bookmark_started_at, bookmark_duration_ms),
        TimePeriod(second_bookmark_started_at, bookmark_duration_ms),
        ]
    assert len(analytics_periods) == 2
    assert len(motion_periods) == 2
    assert not _periods_overlap(chain(analytics_periods, motion_periods, bookmark_periods))
    api.add_bookmark(
        camera_id,
        'test_bookmark_1',
        start_time_ms=first_bookmark_started_at,
        duration_ms=1000)
    api.add_bookmark(
        camera_id,
        'test_bookmark_2',
        start_time_ms=second_bookmark_started_at,
        duration_ms=1000)


def _periods_overlap(periods: Iterable[TimePeriod]):
    sorted_periods = sorted(periods, key=lambda p: p.start_ms)
    current_period = sorted_periods.pop(0)
    for next_period in sorted_periods:
        if next_period.start_ms < current_period.start_ms + current_period.duration_sec * 1000:
            return True
        current_period = next_period
    return False


def archive_is_backed_up(camera_archive, time_period):
    for _ in range(10):  # Make sure archive wasn't backed up after a while
        periods_low = camera_archive.low().list_periods()
        periods_high = camera_archive.high().list_periods()
        both_qualities_periods = [*periods_low, *periods_high]
        all_periods_are_complete = all(period.complete for period in both_qualities_periods)
        if all_periods_are_complete and time_period.is_among(both_qualities_periods):
            return True
        time.sleep(1)
    return False


def wait_until_cameras_in_status(api: MediaserverApi, camera_ids: set[UUID], status: str):
    finished_at = time.monotonic() + 5
    while True:
        all_cameras = api.list_cameras()
        statuses = Counter([camera.status for camera in all_cameras if camera.id in camera_ids])
        if statuses.get(status, 0) == len(all_cameras):
            break
        if time.monotonic() > finished_at:
            raise RuntimeError(f"Timeout waiting for cameras to get the status {status}")
        time.sleep(0.5)
