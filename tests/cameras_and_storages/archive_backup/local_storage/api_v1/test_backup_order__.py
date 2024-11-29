# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math
import time
from contextlib import contextmanager

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import MediaserverApiV1
from mediaserver_api import TimePeriod
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage
from tests.cameras_and_storages.archive_backup.local_storage.common import wait_until_cameras_in_status


def _test_backup_order(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    license_server = LocalLicenseServer()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({'mediaFileDuration': 1})
    mediaserver.start(already_started_ok=True)
    api: MediaserverApiV1 = mediaserver.api
    with license_server.serving():
        api.setup_local_system({'licenseServer': license_server.url()}, basic_and_digest_auth_required=False)
        grant_license(mediaserver, license_server)
    storage = add_backup_storage(one_mediaserver.mediaserver(), one_mediaserver.vm().vm_control, 'V', 20_000)
    backup_archive = one_mediaserver.mediaserver().archive(storage.path)
    camera_server = MultiPartJpegCameraServer()

    [camera_one, camera_two] = add_cameras(mediaserver, camera_server, indices=(0, 1))
    api.enable_secondary_stream(camera_one.id)
    api.enable_secondary_stream(camera_two.id)
    [camera_one_first_period, _] = record_from_cameras(
        api, [camera_one, camera_two], camera_server, duration_sec=10)

    api.set_backup_quality_for_newly_added_cameras(low=True, high=True)
    api.set_backup_all_archive(camera_one.id)
    with _lower_backup_bandwidth(api):
        api.enable_backup_for_cameras([camera_one.id])
        api.wait_for_backup_progress(camera_one.id)
        backup_camera_one_archive = backup_archive.camera_archive(camera_one.physical_id)
        [camera_one_low_history, camera_one_high_history] = _collect_archive_periods_history(
            backup_camera_one_archive)
    assert _period_was_backed_up_continuously(camera_one_low_history)
    assert _period_was_backed_up_continuously(camera_one_high_history)
    assert _backup_starts_from_the_oldest_chunk(camera_one_low_history, camera_one_first_period)
    assert _backup_starts_from_the_oldest_chunk(camera_one_high_history, camera_one_first_period)
    api.wait_for_backup_finish()
    camera_one_low_periods = backup_camera_one_archive.low().list_periods()
    camera_one_high_periods = backup_camera_one_archive.high().list_periods()
    assert camera_one_first_period.is_among(camera_one_low_periods)
    assert camera_one_first_period.is_among(camera_one_high_periods)
    backup_camera_two_archive = backup_archive.camera_archive(camera_two.physical_id)
    camera_two_low_periods = backup_camera_two_archive.low().list_periods()
    camera_two_high_periods = backup_camera_two_archive.high().list_periods()
    assert not camera_two_low_periods
    assert not camera_two_high_periods

    with _lower_backup_bandwidth(api):
        api.enable_backup_for_cameras([camera_two.id])
        with camera_server.async_serve():
            api.start_recording(camera_one.id, camera_two.id)
            wait_until_cameras_in_status(api, {camera_one.id, camera_two.id}, 'Recording')
            [camera_two_low_history, camera_two_high_history] = _collect_archive_periods_history(
                backup_camera_two_archive)
            api.stop_recording(camera_one.id)
            api.stop_recording(camera_two.id)
            wait_until_cameras_in_status(api, {camera_one.id, camera_two.id}, 'Online')
    api.wait_for_backup_finish()
    assert _two_periods_were_backed_up_consistently(camera_two_low_history)
    assert _two_periods_were_backed_up_consistently(camera_two_high_history)
    [camera_two_split_periods] = api.list_recorded_periods([camera_two.id])
    camera_two_periods = TimePeriod.consolidate(camera_two_split_periods, tolerance_sec=1)
    assert _backup_starts_from_the_oldest_chunk(camera_two_low_history, *camera_two_periods)
    assert _backup_starts_from_the_oldest_chunk(camera_two_high_history, *camera_two_periods)

    camera_one_lows_periods = backup_camera_one_archive.low().list_periods()
    camera_one_highs_periods = backup_camera_one_archive.high().list_periods()
    camera_one_lows_periods = TimePeriod.consolidate(camera_one_lows_periods, tolerance_sec=1)
    camera_one_highs_periods = TimePeriod.consolidate(camera_one_highs_periods, tolerance_sec=1)
    [camera_one_split_periods] = api.list_recorded_periods([camera_one.id])
    camera_one_periods = TimePeriod.consolidate(camera_one_split_periods, tolerance_sec=1)
    [camera_one_first_period, camera_one_second_period] = camera_one_periods
    assert camera_one_first_period.is_among(camera_one_lows_periods)
    assert camera_one_first_period.is_among(camera_one_highs_periods)
    # Tolerance is increased because backup for the second video enables during on recording.
    assert camera_one_second_period.is_among(camera_one_lows_periods, tolerance_sec=3)
    assert camera_one_second_period.is_among(camera_one_highs_periods, tolerance_sec=3)
    camera_two_low_periods = backup_camera_two_archive.low().list_periods()
    camera_two_high_periods = backup_camera_two_archive.high().list_periods()
    camera_two_low_periods = TimePeriod.consolidate(camera_two_low_periods, tolerance_sec=1)
    camera_two_high_periods = TimePeriod.consolidate(camera_two_high_periods, tolerance_sec=1)
    [camera_two_split_periods] = api.list_recorded_periods([camera_two.id])
    camera_two_periods = TimePeriod.consolidate(camera_two_split_periods, tolerance_sec=1)
    [camera_two_first_period, camera_two_second_period] = camera_two_periods
    assert camera_two_first_period.is_among(camera_two_low_periods, tolerance_sec=2)
    assert camera_two_first_period.is_among(camera_two_high_periods, tolerance_sec=2)
    assert camera_two_second_period.is_among(camera_two_low_periods, tolerance_sec=3)
    assert camera_two_second_period.is_among(camera_two_high_periods, tolerance_sec=3)


@contextmanager
def _lower_backup_bandwidth(api):
    api.limit_backup_bandwidth(bytes_per_sec=125 * 1000)
    yield
    api.set_unlimited_backup_bandwidth()


def _collect_archive_periods_history(camera_archive):
    low_history = []
    high_history = []
    for _ in range(100):
        low_history.append(camera_archive.low().list_periods())
        high_history.append(camera_archive.high().list_periods())
        time.sleep(0.1)
    return low_history, high_history


def _backup_starts_from_the_oldest_chunk(backup_periods_history, first_period, second_period=None):
    for backup_periods in backup_periods_history:
        consolidated = TimePeriod.consolidate(backup_periods, tolerance_sec=2)
        if len(consolidated) == 1:
            [backup_period] = consolidated
            if not _periods_start_at_the_same_time(first_period, backup_period):
                return False
        else:
            [first_backup_period, second_backup_period] = consolidated
            if not _periods_start_at_the_same_time(first_period, first_backup_period):
                return False
            if not _periods_start_at_the_same_time(second_period, second_backup_period):
                return False
    return True


def _periods_start_at_the_same_time(recorded_period, storage_period):
    expected_timestamp = recorded_period.start.timestamp()
    actual_timestamp = storage_period.start.timestamp()
    return math.isclose(expected_timestamp, actual_timestamp, abs_tol=2)


def _period_was_backed_up_continuously(periods_history):
    for periods in periods_history:
        if len(periods) != 1:
            return False
    return True


def _two_periods_were_backed_up_consistently(backup_periods_history):
    second_period_backup_is_started = False
    for periods in backup_periods_history:
        periods_count = len(periods)
        if periods_count == 1:
            if second_period_backup_is_started:
                return False
        elif periods_count == 2:
            [first_backup_period, _] = periods
            if not first_backup_period.complete:
                return False
            second_period_backup_is_started = True
        else:
            return False
    return True
