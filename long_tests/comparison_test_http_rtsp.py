# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import sys
import time
from collections import Counter
from collections.abc import Mapping
from collections.abc import Sequence
from contextlib import ExitStack
from ipaddress import IPv4Network
from typing import Any
from typing import NamedTuple
from urllib.parse import urlparse

from directories import get_run_dir
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.right_panel_widget import RightPanelWidget
from gui.testkit.hid import HID
from long_tests._common import get_build_info
from long_tests._common import get_installers_url
from long_tests._common import license_server_running
from long_tests._run_single_test import ComparisonTest
from long_tests._run_single_test import run_test
from long_tests._run_single_test import select_comparison_test
from long_tests._vm_pool import BenchmarkStand
from long_tests._vm_pool import VMPool
from mediaserver_api import MotionParameters
from mediaserver_scenarios.provisioned_mediaservers import OneMediaserverStand
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras_hi_low
from os_access import RemotePath
from vm.default_vm_pool import vm_types
from vm.networks import setup_flat_network


@ComparisonTest('comparison_http_rtsp')
def test_4_cameras_1800s(exit_stack: ExitStack) -> Mapping[str, Any]:
    return _comparison_test_http_rtsp_requests(
        exit_stack=exit_stack,
        cameras_count=4,
        duration_sec=1800,
        )


def _comparison_test_http_rtsp_requests(
        exit_stack: ExitStack,
        cameras_count: int,
        duration_sec: int,
        ) -> Mapping[str, Any]:
    # See: https://networkoptix.atlassian.net/wiki/spaces/SD/pages/2899542033/
    vm_pool = VMPool(get_run_dir(), get_installers_url())
    vm_type = vm_types['ubuntu22']
    mediaserver_stand: OneMediaserverStand = exit_stack.enter_context(
        vm_pool.mediaserver_stand(vm_type, ['stub']))
    client_stand = exit_stack.enter_context(vm_pool.client_stand())
    benchmark_stand: BenchmarkStand = exit_stack.enter_context(vm_pool.benchmark_stand())
    [[ip_server, ip_benchmark, _], _] = setup_flat_network(
        (mediaserver_stand.vm(), benchmark_stand.vm(), client_stand.vm()), IPv4Network('10.254.254.0/28'))
    license_key = exit_stack.enter_context(license_server_running(mediaserver_stand.mediaserver()))
    _logger.info('Start and enable recording for %d cameras', cameras_count)
    exit_stack.enter_context(similar_playing_testcameras_hi_low(
        'samples/hi.ts', 'samples/lo.ts', cameras_count, benchmark_stand.installation()))
    cameras = mediaserver_stand.api().add_test_cameras(
        0, cameras_count, address=ip_benchmark)
    engine_collection = mediaserver_stand.api().get_analytics_engine_collection()
    engine_object_detection = engine_collection.get_stub('Object Detection')
    for camera in cameras:
        mediaserver_stand.api().enable_device_agent(engine_object_detection, camera.id)
    mediaserver_stand.api().setup_recording(
        *[camera.id for camera in cameras],
        fps=30,
        motion_params=MotionParameters('9,0,0,44,32', 0, 20),
        enable_recording=True,
        )
    testkit_api = client_stand.start_desktop_client(
        mediaserver_stand.api().get_credentials().username,
        mediaserver_stand.api().get_credentials().password,
        ip_server,
        )
    hid = HID(testkit_api)
    rtree = ResourceTree(testkit_api, hid)
    right_panel = RightPanelWidget(testkit_api, hid)
    right_panel.open_motion_tab()
    for camera in cameras:
        camera_scene_item = rtree.get_camera(camera.name).open()
        camera_scene_item.wait_for_accessible()
    _logger.info('Start measurement')
    time.sleep(duration_sec)
    _logger.info('Finish measurement')
    string_replacement = []
    for num, camera in enumerate(cameras):
        string_replacement.append((f'%7B{str(camera.id)}%7D', f'CAMERA_{num}'))
        string_replacement.append((str(camera.id), f'CAMERA_{num}'))
    string_replacement.append((f'%7B{str(mediaserver_stand.mediaserver().get_mediaserver_guid())}%7D', 'SERVER_ID'))
    string_replacement.append((str(mediaserver_stand.mediaserver().get_mediaserver_guid()), 'SERVER_ID'))
    string_replacement.append((license_key, 'LICENSE_KEY'))
    string_replacement.append((str(engine_object_detection.id()), 'ENGINE_ID'))
    version = mediaserver_stand.mediaserver().get_version()
    string_replacement.append((version.as_str, 'VERSION'))
    requests = Counter()
    for zip_file in mediaserver_stand.mediaserver().list_log_files('http*.zip'):
        _logger.info('Found an HTTP zip log file: %s', zip_file)
        mediaserver_stand.mediaserver().os_access.unzip(zip_file, zip_file.parent)
        zip_file.unlink()
    for log_file in mediaserver_stand.mediaserver().list_log_files('http*.log'):
        _logger.info('Found an HTTP log file: %s', log_file)
        one_log_requests = _parse_http_log(log_file, string_replacement)
        requests.update(one_log_requests)
    if not requests:
        raise RuntimeError('No HTTP/RTSP requests found in http.log')
    records = [{**request._asdict(), 'count': count} for request, count in requests.items()]
    result = {
        'stand': {
            'CPU': vm_type._cpu_count,
            'RAM': vm_type._ram_mb,
            },
        'OS': vm_type._name,
        'test_duration_sec': duration_sec,
        **get_build_info(mediaserver_stand.mediaserver()),
        'measures': records,
        }
    return result


def _parse_http_log(
        log_file: RemotePath,
        replace_parts: Sequence[tuple[str, str]],
        ) -> Mapping['_RequestInfo', int]:
    requests = Counter()
    log_txt = log_file.read_text(encoding='utf-8')
    log_txt_filtered = [line for line in log_txt.splitlines() if 'HTTP' in line or 'RTSP' in line]
    pattern = re.compile(r'(\w+) (\S+) (HTTP|RTSP)/\d+.*$')
    for line in log_txt_filtered:
        record = pattern.search(line)
        if record is None:
            continue
        url = record[2]
        for pair in replace_parts:
            url = url.replace(*pair)
        info = _RequestInfo(method=record[1], path=_normalize_path(url), protocol=record[3])
        if info in requests:
            requests[info] += 1
        else:
            requests[info] = 1
    return requests


def _normalize_path(path: str) -> str:
    parsed_url = urlparse(path)
    parameters = parsed_url.query.split('&')
    for i, parameter in enumerate(parameters):
        if '=' not in parameter:
            continue
        [name, value] = parameter.split('=')
        try:
            int(value)
        except ValueError:
            pass
        else:
            parameters[i] = f'{name}={name.upper()}_VALUE'
    query_url = '&'.join(parameters)
    path = f'{parsed_url.path}?{query_url}' if query_url != '' else parsed_url.path
    path = re.sub(r'\d+\.\d+\.\d+\.\d+', 'NXWITNESS_VERSION', path)
    path = re.sub(r'/chunks/\d+\?', '/chunks/CHUNKS_VALUE?', path)
    return path


class _RequestInfo(NamedTuple):
    method: str
    path: str
    protocol: str


if __name__ == '__main__':
    _logger = logging.getLogger(__name__)
    exit(run_test(select_comparison_test(sys.argv[1:], [
        test_4_cameras_1800s,
        ])))
