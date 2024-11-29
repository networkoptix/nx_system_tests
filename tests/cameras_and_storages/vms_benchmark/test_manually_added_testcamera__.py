# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import ip_network

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import TestCameraConfig
from installation import install_vms_benchmark
from mediaserver_api import CameraStatus
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cameras_and_storages.vms_benchmark.conftest import fetch_testcamera_sample_videos
from tests.cameras_and_storages.vms_benchmark.conftest import layout_for_testcamera
from tests.cameras_and_storages.vms_benchmark.conftest import upload_testcamera_sample_videos


# Check if test camera works as expected by scalability tests - can be attached directly to required mediaserver.
# Test camera does not work on separate windows VM, probably because of firewall issues. Scalability tests
# do not need windows any way, so we test only linux variant.
# TODO: Move from saveCamera to manualCamera/add after VMS-15884 (test_camera support for this) is done.
def _test_manually_added_testcamera(distrib_url, api_version, exit_stack):
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
    server_list = [server for alias, server in sorted(system.items())]

    camera_list = []
    for camera_idx, server in zip(range(camera_count), server_list):
        server.allow_testcamera_discovery(test_camera_app.discovery_port)
        [camera] = server.api.add_test_cameras(offset=camera_idx, count=1, address=camera_addr)
        camera_list.append(camera)

    for camera, server in zip(camera_list, server_list):
        server.api.wait_for_camera_status(camera.id, CameraStatus.OFFLINE, timeout_sec=120)

    with test_camera_app.running():

        for camera, server in zip(camera_list, server_list):
            server.api.wait_for_camera_status(camera.id, CameraStatus.ONLINE, timeout_sec=120)

        for camera, server in zip(camera_list, server_list):
            camera_info = server.api.get_camera(camera.physical_id, is_uuid=False)
            assert camera_info.parent_id == server.api.get_server_id()

        # Use any of cameras for recording.
        camera = camera_list[3]
        server = server_list[3]
        with server.api.camera_recording(camera.id):
            time.sleep(30)  # TODO: FT-855: Check repeatedly for a new period.

        [[period]] = server.api.list_recorded_periods([camera.id])
