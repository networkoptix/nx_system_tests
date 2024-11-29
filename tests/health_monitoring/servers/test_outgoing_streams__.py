# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from contextlib import contextmanager

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.video.ffprobe import get_stream_async
from doubles.video.ffprobe import wait_for_stream
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.health_monitoring.common import configure_mediaserver_with_mjpeg_cameras


def _get_stream_count(mediaserver_api, server_id):
    data = mediaserver_api.get_metrics('servers', server_id)
    return {'primary': data['primary_streams'], 'secondary': data['secondary_streams']}


@contextmanager
def detect_stream(mediaserver_api, server_id, stream, stream_count=1):
    stream = f'{stream}_streams'
    mediaserver_api.wait_for_metric('servers', server_id, stream, expected=stream_count)
    try:
        yield
    finally:
        mediaserver_api.wait_for_metric('servers', server_id, stream, expected=0)


def _test_outgoing_streams(distrib_url, one_vm_type, api_version, camera_count, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    license_server = LocalLicenseServer()
    [camera_server, cameras] = configure_mediaserver_with_mjpeg_cameras(
        license_server, mediaserver, camera_count)
    [camera] = cameras
    mediaserver.api.enable_secondary_stream(camera.id)
    server_id = mediaserver.api.get_server_id()
    [time_period] = record_from_cameras(mediaserver.api, [camera], camera_server, 10)
    exit_stack.enter_context(camera_server.async_serve())
    actual_streams = {'no_streams': _get_stream_count(mediaserver.api, server_id)}
    for stream in ('primary', 'secondary'):
        rtsp_stream = mediaserver.api.rtsp_url(camera.id, stream=stream)
        wait_for_stream(rtsp_stream)
        exit_stack.enter_context(get_stream_async(rtsp_stream, duration_sec=5))
        with detect_stream(mediaserver.api, server_id, stream):
            actual_streams[f'{stream}_streams'] = _get_stream_count(mediaserver.api, server_id)
        rtsp_archive = mediaserver.api.rtsp_url(camera.id, stream=stream, period=time_period)
        wait_for_stream(rtsp_archive)
        exit_stack.enter_context(get_stream_async(rtsp_archive, duration_sec=5))
        with detect_stream(mediaserver.api, server_id, stream):
            actual_streams[f'{stream}_archive_streams'] = _get_stream_count(
                mediaserver.api, server_id)
        for _ in range(3):
            exit_stack.enter_context(get_stream_async(rtsp_stream, duration_sec=5))
        for _ in range(2):
            exit_stack.enter_context(get_stream_async(rtsp_archive, duration_sec=5))
        with detect_stream(mediaserver.api, server_id, stream, stream_count=5):
            actual_streams[f'multiple_{stream}'] = _get_stream_count(
                mediaserver.api, server_id)
    expected_streams = {
        'no_streams': {'primary': 0, 'secondary': 0},
        'primary_streams': {'primary': 1, 'secondary': 0},
        'primary_archive_streams': {'primary': 1, 'secondary': 0},
        'secondary_streams': {'primary': 0, 'secondary': 1},
        'secondary_archive_streams': {'primary': 0, 'secondary': 1},
        'multiple_primary': {'primary': 5, 'secondary': 0},
        'multiple_secondary': {'primary': 0, 'secondary': 5},
        }
    assert actual_streams == expected_streams
