# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from doubles.video.ffprobe import get_media_format_info
from doubles.video.ffprobe import get_stream_info
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras


def _test_mp4_export(distrib_url, one_vm_type, api_version, exit_stack):
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
    [period] = record_from_cameras(api, [camera], camera_server, duration_sec=10)
    url = api.mp4_url(camera.id, period)
    format_info = get_media_format_info(url)
    # There is a group of highly similar formats, such that ffprobe doesn't
    # distinguish among them: format_name contains "mov,mp4,m4a,3gp,3g2,mj2".
    format_names = format_info['format_name'].split(',')
    assert 'mp4' in format_names
    [stream_info] = get_stream_info(url)
    assert stream_info['codec_name'] == 'mjpeg'
