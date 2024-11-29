# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from doubles.video.ffprobe import get_stream_info
from mediaserver_api import TimePeriod


def _media_stream_url(mediaserver_api, stream_type, camera_id, period):
    assert stream_type in ['rtsp', 'webm', 'hls', 'direct-hls']
    if stream_type == 'webm':
        return mediaserver_api.webm_url(camera_id, period)
    if stream_type == 'rtsp':
        return mediaserver_api.rtsp_url(camera_id, period)
    if stream_type == 'hls':
        return mediaserver_api.hls_url(camera_id, period)
    if stream_type == 'direct-hls':
        return mediaserver_api.direct_hls_url(camera_id, period)


# https://networkoptix.atlassian.net/browse/TEST-181
# https://networkoptix.atlassian.net/wiki/spaces/SD/pages/23920667/Media+stream+loading+test
def assert_server_stream(server, camera, sample_media_file, stream_type, artifacts_dir, start_time):
    [periods] = server.api.list_recorded_periods([camera.id], empty_ok=False)
    period = TimePeriod.from_datetime(start_time, sample_media_file.duration)
    assert period in periods
    stream_url = _media_stream_url(server.api, stream_type, camera.id, period)
    local_dir = artifacts_dir / 'stream-media-{}'.format(stream_type)
    local_dir.mkdir(parents=True, exist_ok=True)
    for metadata in get_stream_info(stream_url):
        assert metadata['width'] == sample_media_file.width
        assert metadata['height'] == sample_media_file.height
