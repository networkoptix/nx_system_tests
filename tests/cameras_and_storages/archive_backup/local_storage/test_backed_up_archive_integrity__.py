# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from doubles.video.multipart_reader import get_frames
from doubles.video.video_compare import match_frames
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage


def _test_backed_up_archive_integrity(distrib_url, one_vm_type, api_version, exit_stack):
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
        api.setup_local_system({'licenseServer': license_server.url()})
        grant_license(mediaserver, license_server)
    add_backup_storage(mediaserver, one_mediaserver.vm().vm_control, 'P', 20_000)
    add_backup_storage(mediaserver, one_mediaserver.vm().vm_control, 'Q', 40_000)

    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_secondary_stream(camera.id)
    api.enable_backup_for_cameras([camera.id])
    [camera_physical_id] = [camera.physical_id for camera in api.list_cameras()]
    [time_period] = record_from_cameras(api, [camera], camera_server, 60)
    api.wait_for_backup_finish()
    url = api.mpjpeg_url(camera.id, time_period)
    auth_header = api.make_auth_header()
    received_frames_before = get_frames(url, auth_header=auth_header)

    mediaserver.default_archive().camera_archive(camera_physical_id).remove()

    # For VMS-30956 troubleshooting purposes rebuilt archive and get periods list. Remove after fix.
    api.rebuild_backup_archive()
    api.list_recorded_periods([camera.id])

    received_frames_after = get_frames(url, auth_header=auth_header)
    [skipped, mismatched] = match_frames(received_frames_before, received_frames_after)
    assert len(skipped) < 10
    assert len(mismatched) < 10
