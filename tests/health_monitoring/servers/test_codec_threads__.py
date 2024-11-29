# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from functools import partial

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import mjpeg_fps
from doubles.video.ffprobe import get_stream_async
from doubles.video.ffprobe import wait_for_stream
from installation import ClassicInstallerSupplier
from mediaserver_api import ApproxRel
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.health_monitoring.common import configure_mediaserver_with_mjpeg_cameras


def _test_codec_threads(distrib_url, one_vm_type, api_version, camera_count, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    license_server = LocalLicenseServer()
    [camera_server, cameras] = configure_mediaserver_with_mjpeg_cameras(
        license_server, mediaserver, camera_count)
    server_id = mediaserver.api.get_server_id()
    frame_size = camera_server.video_source.frame_size
    px_per_sec = frame_size[0] * frame_size[1] * mjpeg_fps
    # Decoding thread check.
    exit_stack.enter_context(camera_server.async_serve())
    wait_for_metric = partial(mediaserver.api.wait_for_metric, 'servers', server_id)
    wait_for_metric('decoding_threads', expected=0)
    wait_for_metric('decoding_speed_pix', expected=0)
    for camera in cameras:
        mediaserver.api.start_recording(camera.id)
    wait_for_metric('decoding_threads', expected=camera_count)
    wait_for_metric(
        'decoding_speed_pix', expected=ApproxRel(camera_count * px_per_sec, 0.05))
    for camera in cameras:
        mediaserver.api.stop_recording(camera.id)
    # Encoding threads check.
    wait_for_metric('encoding_threads', expected=0)
    wait_for_metric('encoding_speed_pix', expected=0)
    rtsp_urls = [
        mediaserver.api.rtsp_url(camera.id, codec='mpeg2video')
        for camera in cameras]
    for url in rtsp_urls:
        wait_for_stream(url)
    for url in rtsp_urls:
        exit_stack.enter_context(get_stream_async(url))
    wait_for_metric('encoding_threads', expected=camera_count)
    wait_for_metric(
        'encoding_speed_pix', expected=ApproxRel(camera_count * px_per_sec, 0.05))
