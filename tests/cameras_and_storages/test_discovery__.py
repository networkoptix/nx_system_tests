# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.dnssd import DNSSDWebService
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from doubles.video.rtsp_client import get_mjpeg_stream_info
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import MediaserversDNSSDScope
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.waiting import wait_for_truthy


def _test_discovery(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = stand.mediaserver()
    mediaserver.start()
    api = stand.api()
    api.setup_local_system({'licenseServer': license_server.url()}, basic_and_digest_auth_required=True)
    grant_license(mediaserver, license_server)
    os = mediaserver.os_access
    local_address = os.source_address()
    camera_name = 'test'
    path = '/{}.mjpeg'.format(camera_name)
    assert not api.list_cameras()
    MediaserversDNSSDScope([mediaserver]).advertise_once([
        DNSSDWebService('camera', local_address, camera_server.port, path)])
    [camera] = wait_for_truthy(api.list_cameras, description="Camera is discovered")
    [period] = record_from_cameras(api, [camera], camera_server, 10, force_disconnect=False)
    assert 9 < period.duration_sec < 12
    stream_url = api.secure_rtsp_url(camera.id, period)
    auth_header = api.make_auth_header()
    stream_info = get_mjpeg_stream_info(stream_url, auth_header)
    assert camera_server.video_source.frame_size == stream_info.frame_size
