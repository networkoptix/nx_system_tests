# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from datetime import datetime
from datetime import timedelta
from typing import Sequence

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import CameraArchive
from installation import ClassicInstallerSupplier
from installation import VideoArchive
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage
from tests.merged_systems.time_synchronization.running_time import wait_until_mediaserver_and_os_time_sync
from tests.waiting import wait_for_truthy


def _test_scheduled_backup(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    license_server = LocalLicenseServer()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({'mediaFileDuration': 1})
    mediaserver.start(already_started_ok=True)
    api = mediaserver.api
    with license_server.serving():
        api.setup_local_system({'licenseServer': license_server.url()}, basic_and_digest_auth_required=False)
        grant_license(mediaserver, license_server)
    storage = add_backup_storage(one_mediaserver.mediaserver(), one_mediaserver.vm().vm_control, 'V', 20_000)
    backup_archive = one_mediaserver.mediaserver().archive(storage.path)
    main_archive = one_mediaserver.mediaserver().default_archive()
    os = mediaserver.os_access

    # Make this test independent of current time.
    api.disable_time_sync()
    hour, minute = 12, 30
    timezone = os.get_datetime().tzinfo
    safe_time = datetime(2020, 7, 1, hour, minute, tzinfo=timezone)
    weekday = safe_time.strftime('%A')
    os.set_datetime(safe_time)
    wait_until_mediaserver_and_os_time_sync(api, os, timeout_sec=5)

    # Backups are enabled by default every day in the backup schedule.
    # Therefore, schedule needs to be cleared first so that the backup
    # does not appear ahead of time.
    api.clear_backup_schedule()

    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_secondary_stream(camera.id)
    [camera_physical_id] = [camera.physical_id for camera in api.list_cameras()]
    api.enable_backup_for_cameras([camera.id])
    record_from_cameras(api, [camera], camera_server, 10)
    camera_archive = main_archive.camera_archive(camera_physical_id)

    tomorrow_datetime = safe_time + timedelta(days=1)
    tomorrow = tomorrow_datetime.strftime('%A')
    api.setup_backup_by_schedule(start_hour=hour, finish_hour=23, days=[tomorrow])
    backup_camera_archive = backup_archive.camera_archive(camera_physical_id)
    assert _camera_archive_is_empty(backup_camera_archive)

    api.setup_backup_by_schedule(start_hour=hour, finish_hour=hour + 1, days=[weekday])
    # FT-1701: Remove when VMS-28543 is done.
    wait_for_truthy(_archive_is_saved, args=[backup_camera_archive])
    assert _archive_is_backed_up_within_timeout(camera_archive, backup_camera_archive)
    backup_camera_archive.remove()

    api.setup_backup_by_schedule(start_hour=hour + 1, finish_hour=23, days=[weekday])
    assert _camera_archive_is_empty(backup_camera_archive)

    api.setup_backup_by_schedule(start_hour=0, finish_hour=hour - 1, days=[weekday])
    assert _camera_archive_is_empty(backup_camera_archive)

    now = os.get_datetime()
    api.setup_backup_by_schedule(start_hour=now.hour + 1, finish_hour=now.hour - 1, days=[weekday])
    assert _camera_archive_is_empty(backup_camera_archive)


def _archive_is_saved(camera_archive):
    periods_low = camera_archive.low().list_periods()
    periods_high = camera_archive.high().list_periods()
    return all([period.complete for period in [*periods_high, *periods_low]])


def _archive_is_backed_up_within_timeout(main_archive: CameraArchive, backup_archive: CameraArchive) -> bool:
    finished_at = time.monotonic() + 30
    tolerance_ms = 500
    while True:
        main_low_length = _archive_records_length(main_archive.low())
        main_high_length = _archive_records_length(main_archive.high())
        backup_low_length = _archive_records_length(backup_archive.low())
        backup_high_length = _archive_records_length(backup_archive.high())
        if all([
            abs(main_low_length - backup_low_length) < tolerance_ms,
            abs(main_high_length - backup_high_length) < tolerance_ms,
                ]):
            return True
        if time.monotonic() > finished_at:
            _logger.debug(
                'Length record in the archive (low, high): %d, %d', main_low_length, main_high_length)
            _logger.debug(
                'Length record in the backup (low, high): %d, %d', backup_low_length, backup_high_length)
            _logger.debug('Files in the main archive:\n%s', '\n'.join(_find_mkv_in_archive(main_archive)))
            _logger.debug('Files in the backup archive:\n%s', '\n'.join(_find_mkv_in_archive(backup_archive)))
            return False
        time.sleep(1)


def _find_mkv_in_archive(camera_archive: CameraArchive) -> Sequence[str]:
    low_quality_files_list = [f'low_quality: {file!s}' for file in camera_archive.low().list_sorted_mkv()]
    high_quality_files_list = [f'high_quality: {file!s}' for file in camera_archive.high().list_sorted_mkv()]
    return [*low_quality_files_list, *high_quality_files_list]


def _archive_records_length(video_archive: VideoArchive) -> int:
    all_length = 0
    all_chunks = [file.stem for file in video_archive.list_sorted_mkv()]
    for chunk in all_chunks:
        if '_' in chunk:
            [_, length] = chunk.split('_')
        else:
            length = 0  # The chunk is not finished yet
        all_length += int(length)
    return all_length


def _camera_archive_is_empty(camera_archive: CameraArchive) -> bool:
    finished_at = time.monotonic() + 10
    while True:
        files = [*camera_archive.low().list_sorted_mkv(), *camera_archive.high().list_sorted_mkv()]
        if files:
            _logger.debug('Found files in the camera archive: %r', files)
            return False
        if time.monotonic() >= finished_at:
            return True
        time.sleep(1)


_logger = logging.getLogger(__name__)
