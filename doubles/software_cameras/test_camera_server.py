# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import default_prerequisite_store
from doubles.software_cameras import H264RtspCameraServer
from doubles.software_cameras import MjpegRtspCameraServer
from doubles.software_cameras import MultiPartJpegCameraServer
from doubles.video.ffprobe import SampleMediaFile
from doubles.video.ffprobe import get_stream_info


def _camera_server_errors(camera_server):
    errors = []
    video_codec = camera_server.codec
    url = f'{camera_server.protocol}://127.0.0.1:{camera_server.port}/0.{video_codec}'
    with camera_server.async_serve():
        [stream_info] = get_stream_info(url)
        if stream_info['codec_name'] != video_codec:
            errors.append(f"Video codec is f{stream_info['codec_name']}, expected {video_codec}")
        if video_codec == 'mjpeg':
            [width, height] = camera_server.video_source.frame_size
            if stream_info['width'] != width or stream_info['height'] != height:
                errors.append(
                    f"Resolution is {stream_info['width']}x{stream_info['height']}, "
                    f"expected {width}x{height}")
        return errors


def test_mpjpeg_mjpeg_camera_server():
    assert not _camera_server_errors(MultiPartJpegCameraServer())


def test_rtsp_mjpeg_camera_server():
    assert not _camera_server_errors(MjpegRtspCameraServer())


def test_rtsp_h264_camera_server():
    sample = SampleMediaFile(default_prerequisite_store.fetch('test-cam/sample_gop_15.264'))
    assert not _camera_server_errors(
        H264RtspCameraServer(source_video_file=sample.path, fps=sample.fps))
