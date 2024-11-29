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
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage
from tests.cameras_and_storages.archive_backup.local_storage.common import backup_archive_size_is_enough
from tests.cameras_and_storages.archive_backup.local_storage.common import compare_streams_properties
from tests.cameras_and_storages.archive_backup.local_storage.common import get_video_properties
from tests.waiting import wait_for_truthy


def _test_correct_finish_after_disable(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    camera_server = MultiPartJpegCameraServer()
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
    [camera_one, camera_two] = add_cameras(mediaserver, camera_server, indices=[0, 1])
    api.enable_secondary_stream(camera_one.id)
    record_from_cameras(api, [camera_one, camera_two], camera_server, duration_sec=15)

    api.limit_backup_bandwidth(bytes_per_sec=125 * 1000)
    api.set_backup_quality_for_newly_added_cameras(low=True, high=True)
    api.set_backup_all_archive(camera_one.id)
    api.set_backup_all_archive(camera_two.id)
    api.enable_backup_for_cameras([camera_one.id, camera_two.id])
    enough_size = 16 * 1024
    wait_for_truthy(
        backup_archive_size_is_enough, args=[backup_archive, camera_one.physical_id, enough_size])
    wait_for_truthy(
        backup_archive_size_is_enough, args=[backup_archive, camera_two.physical_id, enough_size])

    api.disable_backup_for_cameras([camera_one.id, camera_two.id])
    camera_one_backup_archive = backup_archive.camera_archive(camera_one.physical_id)
    camera_two_backup_archive = backup_archive.camera_archive(camera_two.physical_id)
    # Wait for the backup to stop
    time.sleep(1)
    camera_one_low_periods_before = camera_one_backup_archive.low().list_periods()
    camera_one_high_periods_before = camera_one_backup_archive.high().list_periods()
    camera_two_low_periods_before = camera_two_backup_archive.low().list_periods()
    camera_two_high_periods_before = camera_two_backup_archive.high().list_periods()
    time.sleep(1)
    camera_one_low_periods_after = camera_one_backup_archive.low().list_periods()
    camera_one_high_periods_after = camera_one_backup_archive.high().list_periods()
    camera_two_low_periods_after = camera_two_backup_archive.low().list_periods()
    camera_two_high_periods_after = camera_two_backup_archive.high().list_periods()
    assert camera_one_low_periods_after == camera_one_low_periods_before
    assert camera_one_high_periods_after == camera_one_high_periods_before
    assert camera_two_low_periods_after == camera_two_low_periods_before
    assert camera_two_high_periods_after == camera_two_high_periods_before

    api.enable_backup_for_cameras([camera_one.id, camera_two.id])
    api.wait_for_backup_finish()
    camera_one_backup_low_periods = camera_one_backup_archive.low().list_periods()
    camera_one_backup_high_periods = camera_one_backup_archive.high().list_periods()
    camera_one_backup_low_periods = TimePeriod.consolidate(
        camera_one_backup_low_periods, tolerance_sec=1)
    camera_one_backup_high_periods = TimePeriod.consolidate(
        camera_one_backup_high_periods, tolerance_sec=1)
    assert len(camera_one_backup_low_periods) == 1
    assert len(camera_one_backup_high_periods) == 1
    main_archive = mediaserver.default_archive()
    camera_one_main_archive = main_archive.camera_archive(camera_one.physical_id)
    [camera_one_main_low_period] = camera_one_main_archive.low().list_periods()
    [camera_one_main_high_period] = camera_one_main_archive.high().list_periods()
    assert camera_one_main_low_period.is_among(camera_one_backup_low_periods)
    assert camera_one_main_high_period.is_among(camera_one_backup_high_periods)
    camera_two_backup_low_periods = camera_two_backup_archive.low().list_periods()
    camera_two_backup_high_periods = camera_two_backup_archive.high().list_periods()
    camera_two_backup_high_periods = TimePeriod.consolidate(
        camera_two_backup_high_periods, tolerance_sec=1)
    assert len(camera_two_backup_low_periods) == 0
    assert len(camera_two_backup_high_periods) == 1
    camera_two_main_archive = main_archive.camera_archive(camera_two.physical_id)
    camera_two_main_low_periods = camera_two_main_archive.low().list_periods()
    [camera_two_main_high_period] = camera_two_main_archive.high().list_periods()
    assert len(camera_two_main_low_periods) == 0
    assert camera_two_main_high_period.is_among(camera_two_backup_high_periods)

    camera_one_main_primary_stream_url = mediaserver.api.mp4_url(
        camera_one.id, camera_one_main_high_period, profile='primary')
    camera_one_main_primary_stream = get_video_properties(
        camera_one_main_primary_stream_url)
    camera_one_main_secondary_stream_url = mediaserver.api.mp4_url(
        camera_one.id, camera_one_main_low_period, profile='secondary')
    camera_one_main_secondary_stream = get_video_properties(
        camera_one_main_secondary_stream_url)
    camera_two_main_primary_stream_url = mediaserver.api.mp4_url(
        camera_two.id, camera_two_main_high_period, profile='primary')
    camera_two_main_primary_stream = get_video_properties(
        camera_two_main_primary_stream_url)

    camera_one_main_archive.remove()
    camera_two_main_archive.remove()
    api.rebuild_main_archive()
    [split_camera_one_period, split_camera_two_period] = api.list_recorded_periods(
        [camera_one.id, camera_two.id])
    [camera_one_period] = TimePeriod.consolidate(split_camera_one_period, tolerance_sec=1)
    [camera_two_period] = TimePeriod.consolidate(split_camera_two_period, tolerance_sec=1)
    assert camera_one_period.is_among(camera_one_backup_low_periods)
    assert camera_one_period.is_among(camera_one_backup_high_periods)
    assert camera_two_period.is_among(camera_two_backup_high_periods)

    [camera_one_backup_high_period] = camera_one_backup_high_periods
    camera_one_backup_primary_stream_url = mediaserver.api.mp4_url(
        camera_one.id, camera_one_backup_high_period, profile='primary')
    camera_one_backup_primary_stream = get_video_properties(
        camera_one_backup_primary_stream_url)
    [camera_one_backup_low_period] = camera_one_backup_low_periods
    streams_comparing_params = dict(bitrate_kbps_rel=0.2, backup_fps_rel=0.2)
    camera_one_primary_stream_different_fields = compare_streams_properties(
        camera_one_main_primary_stream,
        camera_one_backup_primary_stream,
        **streams_comparing_params,
        )
    assert not camera_one_primary_stream_different_fields
    camera_one_backup_secondary_stream_url = mediaserver.api.mp4_url(
        camera_one.id, camera_one_backup_low_period, profile='secondary')
    camera_one_backup_secondary_stream = get_video_properties(
        camera_one_backup_secondary_stream_url)
    camera_one_secondary_stream_different_fields = compare_streams_properties(
        camera_one_main_secondary_stream,
        camera_one_backup_secondary_stream,
        **streams_comparing_params,
        )
    assert not camera_one_secondary_stream_different_fields
    [camera_two_backup_high_period] = camera_two_backup_high_periods
    camera_two_backup_primary_stream_url = mediaserver.api.mp4_url(
        camera_two.id, camera_two_backup_high_period, profile='primary')
    camera_two_backup_primary_stream = get_video_properties(
        camera_two_backup_primary_stream_url)
    camera_two_primary_stream_different_fields = compare_streams_properties(
        camera_two_main_primary_stream,
        camera_two_backup_primary_stream,
        **streams_comparing_params,
        )
    assert not camera_two_primary_stream_different_fields
