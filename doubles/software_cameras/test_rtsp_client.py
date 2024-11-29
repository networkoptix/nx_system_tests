# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math
from concurrent.futures.thread import ThreadPoolExecutor
from contextlib import contextmanager

from doubles.software_cameras import MjpegRtspCameraServer
from doubles.software_cameras import MotionJpegStream
from doubles.video.rtsp_client import ConnectionClosedByServer
from doubles.video.rtsp_client import get_mjpeg_stream_info
from doubles.video.rtsp_client import get_rtsp_stream
from tests.infra import assert_raises

_test_camera = 'test_camera'
_stream_duration = 3


@contextmanager
def serve(camera_server, time_limit_sec):
    with ThreadPoolExecutor(max_workers=1) as executor:
        serve_fut = executor.submit(camera_server.serve, time_limit_sec)
        yield
        serve_fut.result(timeout=2)  # Serving should be stopped by now


def test_getting_stream_by_exact_length():
    camera_server = MjpegRtspCameraServer()
    url = f'{camera_server.protocol}://127.0.0.1:{camera_server.port}/{_test_camera}.mjpeg'
    with serve(camera_server, time_limit_sec=_stream_duration):
        get_rtsp_stream(url, time_limit_sec=_stream_duration)


def test_getting_partial_stream():
    camera_server = MjpegRtspCameraServer()
    url = f'{camera_server.protocol}://127.0.0.1:{camera_server.port}/{_test_camera}.mjpeg'
    with serve(camera_server, time_limit_sec=_stream_duration):
        get_rtsp_stream(url, time_limit_sec=_stream_duration - 1)


def test_getting_whole_stream():
    camera_server = MjpegRtspCameraServer()
    url = f'{camera_server.protocol}://127.0.0.1:{camera_server.port}/{_test_camera}.mjpeg'
    with serve(camera_server, time_limit_sec=_stream_duration):
        get_rtsp_stream(url)


def test_getting_longer_duration():
    camera_server = MjpegRtspCameraServer()
    url = f'{camera_server.protocol}://127.0.0.1:{camera_server.port}/{_test_camera}.mjpeg'
    with serve(camera_server, time_limit_sec=_stream_duration):
        with assert_raises(ConnectionClosedByServer):
            get_rtsp_stream(url, time_limit_sec=_stream_duration + 1)


def test_frames_not_corrupted():
    camera_server = MjpegRtspCameraServer()
    url = f'{camera_server.protocol}://127.0.0.1:{camera_server.port}/{_test_camera}.mjpeg'
    with serve(camera_server, time_limit_sec=_stream_duration):
        frames_received = get_rtsp_stream(url, time_limit_sec=2)
    [frames_sent] = camera_server.get_frames([f'/{_test_camera}.mjpeg'])
    assert len(frames_received) > 0
    assert len(frames_sent) == len(frames_received)
    for sent, received in zip(frames_sent, frames_received):
        assert sent == received


def test_get_mjpeg_stream_info():
    frame_size = (640, 320)
    stream = MotionJpegStream(frame_size)
    camera_server = MjpegRtspCameraServer(video_source=stream)
    url = f'{camera_server.protocol}://127.0.0.1:{camera_server.port}/{_test_camera}.mjpeg'
    with serve(camera_server, time_limit_sec=6):
        info = get_mjpeg_stream_info(url)
    assert math.isclose(info.fps, stream.fps, rel_tol=0.1)
    assert info.frame_size == frame_size


def test_get_mjpeg_stream_info_abruptly_end():
    frame_size = (640, 320)
    stream = MotionJpegStream(frame_size)
    camera_server = MjpegRtspCameraServer(video_source=stream)
    url = f'{camera_server.protocol}://127.0.0.1:{camera_server.port}/{_test_camera}.mjpeg'
    with serve(camera_server, time_limit_sec=3):
        info = get_mjpeg_stream_info(url)
    assert math.isclose(info.fps, stream.fps, rel_tol=0.1)
    assert info.frame_size == frame_size
