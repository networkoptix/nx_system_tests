# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MjpegRtspCameraServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import CameraStatus
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import serve_until_status


def _test_camera_auth(distrib_url, one_vm_type, api_version, camera_server_type, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    if camera_server_type == 'mpjpeg':
        camera_server = MultiPartJpegCameraServer()
    elif camera_server_type == 'rtsp_mjpeg':
        camera_server = MjpegRtspCameraServer()
    else:
        raise RuntimeError(f"Unknown camera_server_type {camera_server_type}")
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    api = one_mediaserver.api()
    api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    user = "DoesNotMatter"
    password = "DoesNotMatter"
    [camera] = add_cameras(mediaserver, camera_server, user=user, password=password)
    serve_until_status(api, camera.id, camera_server, CameraStatus.ONLINE)
