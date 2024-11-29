# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import time
from typing import Any
from typing import Generator
from typing import Optional
from typing import TypeVar
from typing import Union

from doubles.video.ffprobe import FfprobeError
from doubles.video.ffprobe import ffprobe_get_video_stream
from doubles.video.ffprobe import ffprobe_watch_video_stream
from real_camera_tests.checks import Failure
from real_camera_tests.checks import Halt
from real_camera_tests.checks import expect_values

_logger = logging.getLogger(__name__)


_FfprobeReturnType = TypeVar('_FfprobeReturnType')


def ffprobe_progress(
        ffprobe_gen: Generator[Any, None, _FfprobeReturnType],
        ) -> Generator[Halt, None, _FfprobeReturnType]:
    while True:
        try:
            update = next(ffprobe_gen)
        except StopIteration as e:
            return e.value
        yield Halt(json.dumps(update, indent=4))


def watch_video_stream(stream_url, video_length_sec) -> Generator[Union[Halt, Failure], None, float]:
    while True:
        ffprobe_gen = ffprobe_watch_video_stream(stream_url, video_length_sec)
        try:
            return (yield from ffprobe_progress(ffprobe_gen))
        except FfprobeError as e:
            yield Failure(repr(e))
            continue


def wait_for_video_settings_change(stream_url, codec, resolution):
    _logger.debug("Waiting for setting %s %s to applied for %s", codec, resolution, stream_url)
    wait_for_params = {'codec': codec, 'resolution': resolution}
    while True:
        ffprobe_gen = ffprobe_get_video_stream(stream_url, frames_to_check=1)
        try:
            parsed = yield from ffprobe_progress(ffprobe_gen)
        except FfprobeError as e:
            yield Failure(repr(e))
            continue
        actual_params = {
            'codec': parsed['codec'],
            'resolution': '{width}x{height}'.format(**parsed['resolution'])}
        errors = expect_values(wait_for_params, actual_params)
        if not errors:
            _logger.debug(
                "Settings %s %s are successfully applied for %s", codec, resolution, stream_url)
            return
        yield Failure(
            f"Some stream params are not set; last errors: {errors}")


def add_camera_manually(
        api,
        url,
        channel: Optional[int] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        ):
    camera_add_gen = api.add_cameras_manually(url, user=user, password=password)
    while True:
        try:
            next(camera_add_gen)
        except StopIteration as e:
            devices = e.value
            break
        yield Halt("Camera with url {} not yet added".format(url))
    if channel is None:
        [camera] = devices
    else:
        camera = devices[channel - 1]
    return camera


def set_logical_id(server, uuid, logical_id):
    server.api.set_camera_logical_id(uuid, logical_id)
    while server.api.get_camera(uuid).logical_id != logical_id:
        yield Failure("Logical id is not set")


def remove_logical_id(api, uuid):
    api.remove_camera_logical_id(uuid)
    while True:
        if api.get_camera(uuid).logical_id is None:
            break
        yield Failure("logicalId is not removed yet")


def wait_for_stream(stream_url, timeout_s: float):
    """Wait for first few frames to make sure that the stream is running.

    Waiting for one frame only may give a false positive
    because the Mediaserver caches one frame to show something in the client.
    """
    started_at = time.monotonic()
    while True:
        ffprobe_gen = ffprobe_get_video_stream(stream_url, frames_to_check=5)
        try:
            one_frame_res = yield from ffprobe_progress(ffprobe_gen)
        except FfprobeError as e:
            yield Failure(repr(e))
            continue
        elapsed_time = time.monotonic() - started_at
        if isinstance(one_frame_res, dict):  # Received stream params
            _logger.debug("First frame received after %ss", elapsed_time)
            return elapsed_time
        if elapsed_time > timeout_s:
            yield Failure(f"First frame was not received in {timeout_s}s")
        yield Halt(f"Waiting for a first frame for {elapsed_time}s")
