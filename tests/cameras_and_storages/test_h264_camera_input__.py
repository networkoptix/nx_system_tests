# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import H264RtspCameraServer
from doubles.video.ffprobe import SampleMediaFile
from doubles.video.ffprobe import get_stream_info
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras


def _test_h264_camera_input(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    api = one_mediaserver.api()
    api.setup_local_system({'licenseServer': license_server.url()}, basic_and_digest_auth_required=True)
    grant_license(mediaserver, license_server)
    camera_count = 5
    media_sample = SampleMediaFile(default_prerequisite_store.fetch('test-cam/sample_gop_15.264'))
    camera_server = H264RtspCameraServer(
        source_video_file=media_sample.path,
        fps=media_sample.fps,
        )
    cameras = add_cameras(mediaserver, camera_server, indices=range(camera_count))
    camera_ids = [camera.id for camera in cameras]
    duration_sec = 30
    periods = record_from_cameras(api, cameras, camera_server, duration_sec=duration_sec)
    assert len(periods) == camera_count
    for [camera_id, period] in zip(camera_ids, periods):
        url = api.rtsp_url(camera_id, period)
        [media_info] = get_stream_info(url)
        assert media_info['codec_name'] == camera_server.codec
