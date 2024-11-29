# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math
import time
from ipaddress import ip_network

from _internal.service_registry import default_prerequisite_store
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from doubles.video.ffprobe import get_stream_info
from installation import ClassicInstallerSupplier
from installation import TestCameraConfig
from installation import install_vms_benchmark
from mediaserver_api import MotionParameters
from mediaserver_api import RecordingType
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.cameras_and_storages.vms_benchmark.conftest import fetch_testcamera_sample_videos
from tests.cameras_and_storages.vms_benchmark.conftest import upload_testcamera_sample_videos
from tests.waiting import wait_for_equal


def _test_take_camera_recording_settings(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    local_sample_paths = fetch_testcamera_sample_videos(default_prerequisite_store)
    network = ip_network('10.254.1.0/24')
    [first_vm_type, second_vm_type] = two_vm_types
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    network_and_system = exit_stack.enter_context(pool.system({
        'machines': [
            dict(alias='test_camera', type='ubuntu22'),
            dict(alias='first', type=first_vm_type),
            dict(alias='second', type=second_vm_type),
            ],
        'networks': {
            str(network): {
                'first': None,
                'second': None,
                'test_camera': None,
                },
            },
        'mergers': [],
        }))
    [system, machines, assignments] = network_and_system
    vms_benchmark_os_access = machines['test_camera'].os_access
    vms_benchmark_installation = install_vms_benchmark(vms_benchmark_os_access, installer_supplier)
    remote_sample_paths = upload_testcamera_sample_videos(local_sample_paths, vms_benchmark_os_access)
    test_camera_app = vms_benchmark_installation.single_testcamera(
        TestCameraConfig(*remote_sample_paths))
    first_mediaserver = system['first']
    second_mediaserver = system['second']
    first_mediaserver.api.set_license_server(license_server.url())
    first_mediaserver.allow_license_server_access(license_server.url())
    brand = first_mediaserver.api.get_brand()
    key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 2})
    first_mediaserver.api.activate_license(key)
    second_mediaserver.api.set_license_server(license_server.url())
    second_mediaserver.allow_license_server_access(license_server.url())
    brand = second_mediaserver.api.get_brand()
    key = license_server.generate({'BRAND2': brand})
    second_mediaserver.api.activate_license(key)
    [camera_address, _] = assignments['test_camera'][network]
    # Add the same camera to both mediaservers.
    [first_camera] = first_mediaserver.api.add_test_cameras(
        offset=0,
        count=1,
        address=camera_address,
        )
    [second_camera] = second_mediaserver.api.add_test_cameras(
        offset=0,
        count=1,
        address=camera_address,
        )
    assert first_camera.id == second_camera.id
    [one, two, shared_camera] = [first_mediaserver, second_mediaserver, first_camera]
    two.allow_testcamera_discovery(test_camera_app.discovery_port)
    [http_link_camera] = add_cameras(one, camera_server, indices=('http_link_camera',))
    first_recording_settings = {
        'recording_type': RecordingType.ALWAYS,
        'fps': 30,
        }
    second_recording_settings = {
        'recording_type': RecordingType.MOTION_ONLY,
        'fps': 15,
        }
    one.api.setup_recording(shared_camera.id, **first_recording_settings)
    one.api.set_camera_preferred_parent(shared_camera.id, one.api.get_server_id())
    # We need to make sure that the first mediaserver saves settings
    # to the camera before the second one. Without this wait,
    # test fails in ubuntu-win combination.
    time.sleep(10)
    # Increase sensitivity to be sure recording starts on enable.
    motion_params = MotionParameters('9,0,0,44,32', 0, 20)
    two.api.setup_recording(
        shared_camera.id,
        **second_recording_settings,
        motion_params=motion_params,
        )
    two.api.set_camera_preferred_parent(shared_camera.id, two.api.get_server_id())
    assert _get_recording_settings(one, shared_camera.id) == first_recording_settings
    one_period = _record_period_from_camera(test_camera_app, one, shared_camera.id)
    assert _get_recording_settings(two, shared_camera.id) == second_recording_settings
    two_period = _record_period_from_camera(
        test_camera_app, two, shared_camera.id, existing_periods=[one_period])
    merge_systems(one, two, take_remote_settings=False, accessible_ip_net=network)
    assert _get_recording_settings(one, shared_camera.id) == second_recording_settings
    assert _get_recording_settings(two, shared_camera.id) == second_recording_settings
    camera_ids = [camera.id for camera in two.api.list_cameras()]
    assert http_link_camera.id in camera_ids
    expected_shared_camera_parent_id = two.api.get_server_id()
    wait_for_equal(
        _get_camera_parent_id,
        expected_shared_camera_parent_id,
        args=(two, shared_camera.id))
    merged_system_period = _record_period_from_camera(
        test_camera_app, one, shared_camera.id, existing_periods=[one_period, two_period])
    one_period_fps = _get_period_fps(one, shared_camera.id, one_period)
    assert math.isclose(one_period_fps, first_recording_settings['fps'], abs_tol=1)
    two_period_fps = _get_period_fps(two, shared_camera.id, two_period)
    assert math.isclose(two_period_fps, second_recording_settings['fps'], abs_tol=1)
    merged_system_period_fps = _get_period_fps(one, shared_camera.id, merged_system_period)
    assert math.isclose(merged_system_period_fps, second_recording_settings['fps'], abs_tol=1)


def _get_recording_settings(server, camera_id):
    camera = server.api.get_camera(camera_id)
    [first_scheduled_task, *_] = camera.schedule_tasks
    return {
        'recording_type': RecordingType(first_scheduled_task['recordingType']),
        'fps': first_scheduled_task['fps'],
        }


def _record_period_from_camera(test_camera, server, camera_id, existing_periods=None):
    with test_camera.running():
        server.api.enable_recording(camera_id)
        time.sleep(20)
        server.api.stop_recording(camera_id)
    if existing_periods is not None:
        existing_periods = [existing_periods]
    [[period]] = server.api.list_recorded_periods(
        [camera_id],
        empty_ok=False,
        incomplete_ok=False,
        skip_periods=existing_periods,
        )
    return period


def _get_camera_parent_id(server, camera_id):
    camera = server.api.get_camera(camera_id)
    return camera.parent_id


def _get_period_fps(server, camera_id, period):
    stream_url = server.api.mp4_url(camera_id, period)
    [metadata, *_] = get_stream_info(stream_url)
    [frames_count, duration_sec] = [int(v) for v in metadata['avg_frame_rate'].split('/')]
    return frames_count / duration_sec
