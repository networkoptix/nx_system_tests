# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math
import time

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import TestCameraConfig
from installation import install_vms_benchmark
from mediaserver_api import CameraStatus
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.cameras_and_storages.vms_benchmark.conftest import fetch_testcamera_sample_videos
from tests.cameras_and_storages.vms_benchmark.conftest import upload_testcamera_sample_videos
from tests.waiting import wait_for_truthy


def _test_autodiscovered_testcamera(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    local_sample_paths = fetch_testcamera_sample_videos(default_prerequisite_store)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    os_access = one_mediaserver.os_access()
    vms_benchmark_installation = install_vms_benchmark(os_access, installer_supplier)
    remote_sample_paths = upload_testcamera_sample_videos(local_sample_paths, os_access)
    test_camera_app = vms_benchmark_installation.single_testcamera(
        TestCameraConfig(*remote_sample_paths))
    server = one_mediaserver.mediaserver()
    server.allow_testcamera_discovery(test_camera_app.discovery_port)
    server.start()
    server.api.setup_local_system()
    with test_camera_app.running():
        [camera] = wait_for_truthy(server.api.list_cameras, description="Camera is discovered")
        server.api.wait_for_camera_status(camera.id, CameraStatus.ONLINE, timeout_sec=60)
        recording_time = 30
        with server.api.camera_recording(camera.id):
            time.sleep(recording_time)  # TODO: FT-855: Check repeatedly for a new period.
        [[period]] = server.api.list_recorded_periods([camera.id], incomplete_ok=False)
        assert math.isclose(period.duration_sec, recording_time, abs_tol=5)
