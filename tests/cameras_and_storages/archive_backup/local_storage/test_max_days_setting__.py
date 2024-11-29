# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from datetime import datetime
from datetime import timedelta
from typing import List

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import MediaserverApi
from mediaserver_api import TimePeriod
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage
from tests.waiting import wait_for_truthy

_logger = logging.getLogger(__name__)


def _test_max_days_setting(distrib_url, one_vm_type, api_version, exit_stack):
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
    [camera] = add_cameras(mediaserver, camera_server)
    mediaserver.api.enable_secondary_stream(camera.id)
    duration_sec = 10
    record_from_cameras(mediaserver.api, [camera], camera_server, duration_sec)
    _change_server_time(mediaserver, timedelta(days=1))
    wait_for_truthy(_periods_appear_after_restart, args=[api, camera.id], timeout_sec=10)
    record_from_cameras(mediaserver.api, [camera], camera_server, duration_sec)
    _change_server_time(mediaserver, timedelta(minutes=10))
    wait_for_truthy(_periods_appear_after_restart, args=[api, camera.id], timeout_sec=10)
    record_from_cameras(mediaserver.api, [camera], camera_server, duration_sec)
    max_days = 1
    _change_server_time(mediaserver, timedelta(days=max_days, minutes=-5))
    wait_for_truthy(_periods_appear_after_restart, args=[api, camera.id], timeout_sec=10)
    default_archive = mediaserver.default_archive()
    main_camera_archive = default_archive.camera_archive(camera.physical_id)
    _main_archive_is_correct(main_camera_archive)
    api.enable_backup_for_cameras([camera.id])
    api.wait_for_backup_finish()
    backup_camera_archive = backup_archive.camera_archive(camera.physical_id)
    _backup_archive_is_correct(main_camera_archive, backup_camera_archive)
    api.set_camera_archive_days(camera.id, max_archive_days=max_days)
    retaining_timestamp = api.get_datetime() - timedelta(days=max_days)

    wait_for_truthy(
        _old_archive_is_removed, args=[main_camera_archive, retaining_timestamp])
    wait_for_truthy(
        _old_archive_is_removed, args=[backup_camera_archive, retaining_timestamp])
    assert len(_all_archive_periods(main_camera_archive)) == 2
    assert len(_all_archive_periods(backup_camera_archive)) == 2


def _periods_appear_after_restart(api: MediaserverApi, camera_id: str) -> bool:
    [loaded_periods] = api.list_recorded_periods([camera_id])
    if loaded_periods:
        return True
    return False


def _main_archive_is_correct(camera_archive):
    periods = [*camera_archive.low().list_periods(), *camera_archive.high().list_periods()]
    if not periods:
        raise RuntimeError('Main archive is empty')


def _backup_archive_is_correct(main_camera_archive, backup_camera_archive):
    main_low_quality = main_camera_archive.low().list_periods()
    main_high_quality = main_camera_archive.high().list_periods()
    backup_low_quality = backup_camera_archive.low().list_periods()
    backup_high_quality = backup_camera_archive.high().list_periods()
    for period in main_low_quality:
        if not period.is_among(backup_low_quality, tolerance_sec=2):
            raise RuntimeError('Backup for low quality is incomplete')
    for period in backup_low_quality:
        if not period.is_among(main_low_quality, tolerance_sec=2):
            raise RuntimeError('Backup for low quality has unexpected data')
    for period in main_high_quality:
        if not period.is_among(backup_high_quality, tolerance_sec=2):
            raise RuntimeError('Backup for high quality is incomplete')
    for period in backup_high_quality:
        if not period.is_among(main_high_quality, tolerance_sec=2):
            raise RuntimeError('Backup for high quality has unexpected data')


def _change_server_time(server, delta: timedelta):
    server.stop()
    server.os_access.shift_time(delta)
    server.start()


def _all_archive_periods(camera_archive) -> List[TimePeriod]:
    low_quality = camera_archive.low().list_periods()
    high_quality = camera_archive.high().list_periods()
    return [*low_quality, *high_quality]


def _old_archive_is_removed(camera_archive, retain_after: datetime):
    for period in _all_archive_periods(camera_archive):
        if period.start < retain_after:
            return False
    return True
