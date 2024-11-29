# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

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
from tests.cameras_and_storages.archive_backup.local_storage.common import record_different_archive_types

_logger = logging.getLogger(__name__)


def _test_motion_and_bookmarks_only(distrib_url, one_vm_type, api_version, exit_stack):
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
        api.setup_local_system({'licenseServer': license_server.url()})
        grant_license(mediaserver, license_server)
    [camera] = add_cameras(mediaserver, high_camera_server)
    camera_address = mediaserver.os_access.source_address()
    secondary_stream_url = '{}://{}:{}/0.mjpeg'.format(
        low_camera_server.protocol, camera_address, low_camera_server.port)
    api.set_secondary_stream(camera.id, secondary_stream_url)
    record_different_archive_types(api, camera.id, high_camera_server, low_camera_server)
    storage = add_backup_storage(one_mediaserver.mediaserver(), one_mediaserver.vm().vm_control, 'V', 20_000)
    one_mediaserver.mediaserver().archive(storage.path)
    api: MediaserverApiV1 = mediaserver.api

    motions_before_rebuild = api.list_motion_periods(camera.id)
    bookmarks_before_backup = api.list_bookmarks(camera.id)
    api.set_backup_content_type(camera.id, [BackupContentType.motion, BackupContentType.bookmarks])
    api.set_backup_quality_for_newly_added_cameras(low=True, high=True)
    api.enable_backup_for_cameras([camera.id])
    api.wait_for_backup_finish()

    mediaserver.default_archive().camera_archive(camera.physical_id).remove()
    api.rebuild_main_archive()
    motions_after_rebuild = api.list_motion_periods(camera.id)
    [first_motion_period_after_rebuild, second_motion_period_after_rebuild] = motions_after_rebuild
    assert first_motion_period_after_rebuild.is_among(motions_before_rebuild)
    assert second_motion_period_after_rebuild.is_among(motions_before_rebuild)
    bookmarks_after_backup = sorted(
        api.list_bookmarks(camera.id),
        key=lambda bookmark: bookmark.name)
    assert bookmarks_after_backup == bookmarks_before_backup
    [archive_periods_after_backup] = api.list_recorded_periods([camera.id])
    [bookmark_one, bookmark_two] = bookmarks_after_backup
    assert bookmark_is_backed_up(bookmark_one, archive_periods_after_backup)
    assert bookmark_is_backed_up(bookmark_two, archive_periods_after_backup)
    # VMS-37387: Analytics recorded period leftover appears after restoring the backup
    if api.server_newer_than('vms_5.0'):
        assert not api.list_analytics_periods(camera.id)
