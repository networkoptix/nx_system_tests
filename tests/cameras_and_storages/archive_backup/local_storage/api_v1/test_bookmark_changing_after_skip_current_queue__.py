# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import BackupContentType
from mediaserver_api import MediaserverApiV1
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage
from tests.cameras_and_storages.archive_backup.local_storage.common import bookmark_is_backed_up


def _test_bookmark_changing_after_skip_current_queue(distrib_url, one_vm_type, api_version, exit_stack):
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
        api.setup_local_system({'licenseServer': license_server.url()}, basic_and_digest_auth_required=False)
        grant_license(mediaserver, license_server)
    storage = add_backup_storage(one_mediaserver.mediaserver(), one_mediaserver.vm().vm_control, 'V', 20_000)
    backup_archive = one_mediaserver.mediaserver().archive(storage.path)
    [camera_one, camera_two] = add_cameras(mediaserver, camera_server, indices=[0, 1])
    api.enable_secondary_stream(camera_one.id)
    api.enable_secondary_stream(camera_two.id)
    [camera_one_period, _] = record_from_cameras(
        api, [camera_one, camera_two], camera_server, 15)

    api.limit_backup_bandwidth(1000**2 / 8)
    video_start_time_ms = int(camera_one_period.start.timestamp() * 1000)
    bookmark_one_id = api.add_bookmark(
        camera_one.id,
        'test_bookmark_one',
        start_time_ms=video_start_time_ms + 9000,
        duration_ms=5000,
        description='bookmark_one_initial')
    api.set_backup_quality_for_newly_added_cameras(low=True, high=True)
    api.set_backup_all_archive(camera_two.id)
    api.enable_backup_for_cameras([camera_two.id])
    api.wait_for_backup_state_changed(camera_two.id, timeout_sec=5)
    backup_camera_two_archive = backup_archive.camera_archive(camera_two.physical_id)
    assert backup_camera_two_archive.low().list_periods()
    assert backup_camera_two_archive.high().list_periods()
    api.skip_all_backup_queues()
    api.update_bookmark_description(
        camera_one.id, bookmark_one_id, new_description='bookmark_one_changed')
    bookmark_two_id = api.add_bookmark(
        camera_one.id,
        'test_bookmark_two',
        start_time_ms=video_start_time_ms,
        duration_ms=5000,
        description='bookmark_two_initial')
    api.set_unlimited_backup_bandwidth()
    api.set_backup_content_type(camera_one.id, [BackupContentType.bookmarks])
    api.enable_backup_for_cameras([camera_one.id])
    api.wait_for_backup_finish()

    mediaserver.default_archive().camera_archive(camera_one.physical_id).remove()
    api.rebuild_main_archive()
    bookmark_one = api.get_bookmark(camera_one.id, bookmark_one_id)
    bookmark_two = api.get_bookmark(camera_one.id, bookmark_two_id)
    [archive_periods_after_rebuild] = api.list_recorded_periods([camera_one.id])
    assert not bookmark_is_backed_up(bookmark_one, archive_periods_after_rebuild)
    assert bookmark_is_backed_up(bookmark_two, archive_periods_after_rebuild)
