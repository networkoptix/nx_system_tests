# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MjpegRtspCameraServer
from doubles.software_cameras import MultiPartJpegCameraServer
from doubles.video.multipart_reader import get_frames
from doubles.video.rtsp_client import get_multiple_rtsp_streams
from doubles.video.video_compare import match_frames
from installation import ClassicInstallerSupplier
from mediaserver_api import MotionType
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras

_logger = logging.getLogger(__name__)


def _test_camera_input(distrib_url, one_vm_type, api_version, camera_count, duration_sec, force_disconnect, camera_server_type, exit_stack):
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
    cameras = add_cameras(mediaserver, camera_server, indices=range(camera_count))
    camera_ids = [camera.id for camera in cameras]
    # TODO: VMS-18345: Remove disabling motion detection for VMS master after fix
    api.set_motion_type_for_cameras(camera_ids, MotionType.NONE)
    new_periods = record_from_cameras(
        api, cameras, camera_server, duration_sec=duration_sec, force_disconnect=force_disconnect)
    new_frames = camera_server.get_frames([camera.path for camera in cameras])
    assert len(new_periods) == camera_count
    if camera_server.protocol == 'rtsp':
        auth_header = api.make_auth_header()
        url_list = [
            api.secure_rtsp_url(camera_id, period)
            for camera_id, period in zip(camera_ids, new_periods)]
        frames_list = get_multiple_rtsp_streams(url_list, auth_header=auth_header)
    else:
        url_list = [
            api.mpjpeg_url(camera_id, period)
            for camera_id, period in zip(camera_ids, new_periods)]
        frames_list = [get_frames(url) for url in url_list]
    for new_period, sent_frames, received_frames in zip(new_periods, new_frames, frames_list):
        # The more cameras the later recording is stopped.
        # Usually it's between 9.99 and 10+0.01*cameras_count.
        # TODO: Find out if it's normal that less was recorded than served.
        assert duration_sec - 2 < new_period.duration_sec < duration_sec * 1.5
        skipped, mismatched = match_frames(sent_frames, received_frames)
        if force_disconnect:  # In disconnecting is not forced, camera server saves more frames
            assert len(received_frames) > 0.9 * len(sent_frames)
            assert len(skipped) < 0.1 * len(sent_frames)
        assert len(mismatched) < 0.1 * len(sent_frames)
