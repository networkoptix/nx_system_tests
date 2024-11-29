# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from functools import partial

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.video.ffprobe import get_stream_async
from doubles.video.ffprobe import wait_for_stream
from installation import ClassicInstallerSupplier
from mediaserver_api import Alarm
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.health_monitoring.common import configure_mediaserver_with_mjpeg_cameras


def _expected_encoding_threads_alarm(thread_count, setting_name):
    return Alarm(
        level='warning',
        text=(
            f'has {thread_count} currently running encoding threads. Recommended number of '
            f'encoding threads: 2. Limit encoding threads number using {setting_name} setting '
            'in Web Admin advanced settings page.'))


def _test_encoding_streams(distrib_url, one_vm_type, api_version, camera_count, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    license_server = LocalLicenseServer()
    [camera_server, cameras] = configure_mediaserver_with_mjpeg_cameras(
        license_server, mediaserver, camera_count)
    setting_name = 'maxHttpTranscodingSessions'
    server_id = mediaserver.api.get_server_id()
    alarm_path = ('servers', server_id, 'load', 'encodingThreads')
    with camera_server.async_serve():
        rtsp_urls = [
            mediaserver.api.rtsp_url(camera.id, codec='mpeg2video')
            for camera in cameras]
        assert mediaserver.api.get_metrics('servers', server_id, 'encoding_threads') == 0
        assert alarm_path not in mediaserver.api.list_metrics_alarms()
        for url in rtsp_urls[:2]:
            wait_for_stream(url)
        for url in rtsp_urls[:2]:
            exit_stack.enter_context(get_stream_async(url, duration_sec=60))
        wait_for_encoding_threads = partial(
            mediaserver.api.wait_for_metric, 'servers', server_id, 'encoding_threads')
        wait_for_encoding_threads(expected=2)
        assert alarm_path not in mediaserver.api.list_metrics_alarms()
        wait_for_stream(rtsp_urls[2])
        exit_stack.enter_context(get_stream_async(rtsp_urls[2], duration_sec=60))
        wait_for_encoding_threads(expected=3)
        alarms = mediaserver.api.list_metrics_alarms()[alarm_path]
        assert _expected_encoding_threads_alarm(3, setting_name) in alarms
        for url in rtsp_urls[3:]:
            wait_for_stream(url)
        for url in rtsp_urls[3:]:
            exit_stack.enter_context(get_stream_async(url, duration_sec=60))
        wait_for_encoding_threads(expected=camera_count)
        assert (
            _expected_encoding_threads_alarm(camera_count, setting_name)
            in mediaserver.api.list_metrics_alarms()[alarm_path])
    wait_for_encoding_threads(timeout_sec=90, expected=0)
    assert alarm_path not in mediaserver.api.list_metrics_alarms()
