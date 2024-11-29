# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import itertools
import sys
import time
from contextlib import contextmanager
from ipaddress import ip_network

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import TestCameraConfig
from installation import install_vms_benchmark
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest
from tests.cameras_and_storages.vms_benchmark.conftest import fetch_testcamera_sample_videos
from tests.cameras_and_storages.vms_benchmark.conftest import layout_for_testcamera
from tests.cameras_and_storages.vms_benchmark.conftest import upload_testcamera_sample_videos
from tests.infra import Failure


@contextmanager
def _live_rtsp_perf_running(vms_benchmark, rtsp_url_list, username, password):
    # To properly exit from test_camera.running() rtsp_perf must be stopped first.
    try:
        yield vms_benchmark.start_rtsp_perf_live(rtsp_url_list, username, password)
    finally:
        vms_benchmark.stop_rtsp_perf()


# Check if rtsp_perf tool works as expected by scalability tests - able to load live rtsp stream from test camera.
class test_v0(VMSTest):
    """Test rtsp perf live.

    Selection-Tag: no_testrail
    """

    def _run(self, args, exit_stack):
        _test_rtsp_perf_live(args.distrib_url, 'v0', exit_stack)


def _test_rtsp_perf_live(distrib_url, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    local_sample_paths = fetch_testcamera_sample_videos(default_prerequisite_store)
    network = ip_network('10.254.1.0/24')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    network_and_system = exit_stack.enter_context(pool.system(layout_for_testcamera(network)))
    [system, machines, assignments] = network_and_system
    vms_benchmark_os_access = machines['test_camera'].os_access
    vms_benchmark_installation = install_vms_benchmark(vms_benchmark_os_access, installer_supplier)
    remote_sample_paths = upload_testcamera_sample_videos(local_sample_paths, vms_benchmark_os_access)
    camera_count = 4
    test_camera_app = vms_benchmark_installation.similar_testcameras(
        TestCameraConfig(*remote_sample_paths), camera_count=camera_count)
    camera_addr, _ = assignments['test_camera'][network]

    rtsp_url_list = []
    alias_it = itertools.cycle(sorted(system))
    for camera_idx, alias in zip(range(camera_count), alias_it):
        server = system[alias]
        [camera] = server.api.add_test_cameras(offset=camera_idx, count=1, address=camera_addr)
        addr, _ = assignments[alias][network]
        rtsp_url_list.append('rtsp://{}:{}/{}'.format(addr, server.port, camera.id))

    some_server_api = list(system.values())[0].api  # all servers are expected to have same password
    credentials = some_server_api.get_credentials()
    username = credentials.username
    password = credentials.password

    with test_camera_app.running():
        started_at = time.monotonic()
        timeout_sec = 60
        with _live_rtsp_perf_running(
                vms_benchmark_installation, rtsp_url_list, username, password) as rtsp_process:
            while True:
                rtsp_perf_statistics = next(rtsp_process)
                if rtsp_perf_statistics.bitrate_mbps > 1:
                    break
                if time.monotonic() - started_at > timeout_sec:
                    raise Failure("rtsp_perf did not start")


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_v0()]))
