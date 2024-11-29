# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from doubles.video.rtsp_client import get_mjpeg_stream_info
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras


def _test_secondary_rtsp_stream(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    api = one_mediaserver.api()
    api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_secondary_stream(camera.id)
    url_primary = api.rtsp_url(camera.id, stream='primary')
    url_secondary = api.rtsp_url(camera.id, stream='secondary')
    auth_header = api.make_auth_header()
    with camera_server.async_serve():
        media_info_primary = get_mjpeg_stream_info(url_primary, auth_header)
        media_info_secondary = get_mjpeg_stream_info(url_secondary, auth_header)
    assert math.isclose(media_info_primary.fps, media_info_secondary.fps, rel_tol=0.1)
    assert media_info_primary.frame_size == media_info_secondary.frame_size
