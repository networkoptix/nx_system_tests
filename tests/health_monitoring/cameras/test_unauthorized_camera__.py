# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import JPEGSequence
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import CameraStatus
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import serve_until_status


def _test_unauthorized_camera(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    api = one_mediaserver.api()
    api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    [user, password] = ['User', 'GoodPassword']
    video_source = JPEGSequence(frame_size=(640, 320))
    camera_server = exit_stack.enter_context(MultiPartJpegCameraServer(
        video_source=video_source, user=user, password=password))
    [camera] = add_cameras(
        mediaserver,
        camera_server,
        user=user,
        password=password)
    api.stop_recording(camera.id)
    api.start_recording(camera.id)
    api.set_camera_credentials(camera.id, 'User', 'WrongPassword')
    min_archive_days = 12
    api.set_camera_archive_days(camera.id, min_archive_days=min_archive_days)
    serve_until_status(api, camera.id, camera_server, CameraStatus.UNAUTHORIZED)
    assert api.get_metrics('system_info', 'cameras') == 1
    camera_metrics = api.get_metrics('cameras', camera.id)
    assert camera_metrics['status'] == CameraStatus.UNAUTHORIZED
    assert 'primary' not in camera_metrics
    assert camera_metrics['min_archive_length_sec'] == min_archive_days * 24 * 3600
