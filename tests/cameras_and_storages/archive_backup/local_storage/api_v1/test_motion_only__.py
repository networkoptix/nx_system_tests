# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import JPEGSequence
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import BackupContentType
from mediaserver_api import MediaserverApiV1
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage
from tests.cameras_and_storages.archive_backup.local_storage.common import bookmark_is_backed_up
from tests.cameras_and_storages.archive_backup.local_storage.common import compare_streams_properties
from tests.cameras_and_storages.archive_backup.local_storage.common import get_video_properties
from tests.cameras_and_storages.archive_backup.local_storage.common import record_different_archive_types


def _test_motion_only(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    license_server = LocalLicenseServer()
    high_camera_server = exit_stack.enter_context(MultiPartJpegCameraServer(video_source=(JPEGSequence(frame_size=(1920, 1080)))))
    low_camera_server = exit_stack.enter_context(MultiPartJpegCameraServer(video_source=(JPEGSequence(frame_size=(854, 480)))))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({'mediaFileDuration': 1})
    mediaserver.enable_optional_plugins(['sample'])
    mediaserver.start(already_started_ok=True)
    api: MediaserverApiV1 = mediaserver.api
    with license_server.serving():
        api.setup_local_system({'licenseServer': license_server.url()}, basic_and_digest_auth_required=True)
        grant_license(mediaserver, license_server)
    [camera] = add_cameras(mediaserver, high_camera_server)
    camera_address = mediaserver.os_access.source_address()
    secondary_stream_url = '{}://{}:{}/0.mjpeg'.format(
        low_camera_server.protocol, camera_address, low_camera_server.port)
    api.set_secondary_stream(camera.id, secondary_stream_url)
    record_different_archive_types(api, camera.id, high_camera_server, low_camera_server)
    storage = add_backup_storage(one_mediaserver.mediaserver(), one_mediaserver.vm().vm_control, 'V', 20_000)
    backup_archive = one_mediaserver.mediaserver().archive(storage.path)
    api: MediaserverApiV1 = mediaserver.api

    [[main_period]] = api.list_recorded_periods([camera.id])
    main_primary_stream_url = mediaserver.api.mp4_url(camera.id, main_period, profile='primary')
    main_primary_stream = get_video_properties(main_primary_stream_url)
    main_secondary_stream_url = mediaserver.api.mp4_url(camera.id, main_period, profile='secondary')
    main_secondary_stream = get_video_properties(main_secondary_stream_url)
    motion_periods_before_rebuild = api.list_motion_periods(camera.id)

    api.set_backup_content_type(camera.id, [BackupContentType.motion])
    api.set_backup_quality_for_newly_added_cameras(low=True, high=True)
    api.enable_backup_for_cameras([camera.id])
    api.wait_for_backup_finish()

    mediaserver.default_archive().camera_archive(camera.physical_id).remove()
    api.rebuild_main_archive()
    motion_periods_after_rebuild = api.list_motion_periods(camera.id)
    first_motion_period_after_rebuild = motion_periods_after_rebuild[0]
    assert first_motion_period_after_rebuild.is_among(motion_periods_before_rebuild)
    second_motion_period_after_rebuild = motion_periods_after_rebuild[1]
    assert second_motion_period_after_rebuild.is_among(motion_periods_before_rebuild)
    assert not api.list_analytics_periods(camera.id)
    bookmarks_after_backup = sorted(
        api.list_bookmarks(camera.id),
        key=lambda bookmark: bookmark.name)
    [archive_periods_after_backup] = api.list_recorded_periods([camera.id])
    [bookmark_one, bookmark_two] = bookmarks_after_backup
    assert not bookmark_is_backed_up(bookmark_one, archive_periods_after_backup)
    assert not bookmark_is_backed_up(bookmark_two, archive_periods_after_backup)

    backup_camera_archive = backup_archive.camera_archive(camera.physical_id)
    backup_low_periods = backup_camera_archive.low().list_periods()
    backup_high_periods = backup_camera_archive.high().list_periods()
    streams_comparing_params = dict(bitrate_kbps_rel=0.2, backup_fps_rel=0.2)
    [first_low_period, second_low_period] = backup_low_periods
    first_low_stream_url = mediaserver.api.mp4_url(
        camera.id, first_low_period, profile='secondary')
    first_low_stream = get_video_properties(first_low_stream_url)
    first_low_streams_diff = compare_streams_properties(
        main_secondary_stream, first_low_stream, **streams_comparing_params)
    [first_low_streams_diff_reason] = first_low_streams_diff.keys()
    assert first_low_streams_diff_reason == 'duration_sec'
    second_low_stream_url = mediaserver.api.mp4_url(
        camera.id, second_low_period, profile='secondary')
    second_low_stream = get_video_properties(second_low_stream_url)
    second_low_streams_diff = compare_streams_properties(
        main_secondary_stream, second_low_stream, **streams_comparing_params)
    [second_low_streams_diff_reason] = second_low_streams_diff.keys()
    assert second_low_streams_diff_reason == 'duration_sec'
    [first_high_period, second_high_period] = backup_high_periods
    first_high_stream_url = mediaserver.api.mp4_url(
        camera.id, first_high_period, profile='primary')
    first_high_stream = get_video_properties(first_high_stream_url)
    first_high_streams_diff = compare_streams_properties(
        main_primary_stream, first_high_stream, **streams_comparing_params)
    [first_high_streams_diff_reason] = first_high_streams_diff.keys()
    assert first_high_streams_diff_reason == 'duration_sec'
    second_high_stream_url = mediaserver.api.mp4_url(
        camera.id, second_high_period, profile='primary')
    second_high_stream = get_video_properties(second_high_stream_url)
    second_high_streams_diff = compare_streams_properties(
        main_primary_stream, second_high_stream, **streams_comparing_params)
    [second_high_streams_diff_reason] = second_high_streams_diff.keys()
    assert second_high_streams_diff_reason == 'duration_sec'