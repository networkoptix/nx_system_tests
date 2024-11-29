# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import MediaserverApiV1
from mediaserver_api import TimePeriod
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage
from tests.cameras_and_storages.archive_backup.local_storage.common import compare_streams_properties
from tests.cameras_and_storages.archive_backup.local_storage.common import get_video_properties


def _test_low_quality_only(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    license_server = LocalLicenseServer()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({'mediaFileDuration': 1})
    mediaserver.start(already_started_ok=True)
    api: MediaserverApiV1 = mediaserver.api
    with license_server.serving():
        api.setup_local_system({'licenseServer': license_server.url()}, basic_and_digest_auth_required=True)
        grant_license(mediaserver, license_server)
    storage = add_backup_storage(one_mediaserver.mediaserver(), one_mediaserver.vm().vm_control, 'V', 20_000)
    backup_archive = one_mediaserver.mediaserver().archive(storage.path)
    camera_server = MultiPartJpegCameraServer()

    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_secondary_stream(camera.id)
    backup_camera_archive = backup_archive.camera_archive(camera.physical_id)
    with camera_server.async_serve():
        api.start_recording(camera.id)
        # Wait for short video is recorded
        time.sleep(5)
        api.set_backup_all_archive(camera.id)
        api.set_backup_quality_for_newly_added_cameras(low=True, high=False)
        api.enable_backup_for_cameras([camera.id])
        _wait_for_online_backup_started(api, camera.id)
        low_archive_files_before = backup_camera_archive.low().list_sorted_mkv()
        # Wait for new chunks are backed up
        time.sleep(5)
        low_archive_files_after = backup_camera_archive.low().list_sorted_mkv()
        api.stop_recording(camera.id)
    assert len(low_archive_files_after) > len(low_archive_files_before)
    api.wait_for_backup_finish()

    [split_period] = api.list_recorded_periods([camera.id])
    [recorded_period] = TimePeriod.consolidate(split_period, tolerance_sec=2)
    low_quality_periods = backup_camera_archive.low().list_periods()
    high_quality_periods = backup_camera_archive.high().list_periods()
    low_quality_periods = TimePeriod.consolidate(low_quality_periods, tolerance_sec=2)
    assert recorded_period.is_among(low_quality_periods, tolerance_sec=2)
    assert not high_quality_periods

    main_stream_url = mediaserver.api.mp4_url(camera.id, recorded_period, profile='secondary')
    streams_comparing_params = dict(bitrate_kbps_rel=0.2, backup_fps_rel=0.2)
    main_secondary_stream_properties = get_video_properties(main_stream_url)
    mediaserver.default_archive().camera_archive(camera.physical_id).remove()
    api.rebuild_main_archive()
    [split_period_after_rebuild] = api.list_recorded_periods([camera.id])
    [period_after_rebuild] = TimePeriod.consolidate(split_period_after_rebuild, tolerance_sec=2)
    assert period_after_rebuild.is_among([recorded_period], tolerance_sec=2)
    backup_stream_url = mediaserver.api.mp4_url(camera.id, period_after_rebuild, profile='secondary')
    backup_primary_stream_properties = get_video_properties(backup_stream_url)
    streams_different_fields = compare_streams_properties(
        main_secondary_stream_properties,
        backup_primary_stream_properties,
        **streams_comparing_params,
        )
    assert not streams_different_fields


def _wait_for_online_backup_started(api: MediaserverApiV1, camera_id):
    timeout_sec = 15
    started_at = time.monotonic()
    while True:
        if api.get_actual_backup_state(camera_id).to_backup == (0, 0):
            return
        if time.monotonic() - started_at > timeout_sec:
            raise RuntimeError("Zero position wasn't reached after timeout")
        time.sleep(0.5)
