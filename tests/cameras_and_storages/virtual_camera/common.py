# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from doubles.video.ffprobe import watch_whole_stream


def watch_video(api, camera_id, period):
    stream_url = api.mkv_url(camera_id, period)
    return watch_whole_stream(stream_url)
