# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import CameraStatus
from mediaserver_api import RecordingStartFailed
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.waiting import wait_for_equal


def _check_resource_count(api, plugin_name, expected_resource_count: tuple):

    def _get_resource_count(api, plugin_name):
        [resource_binding_info] = api.get_plugin_info(plugin_name)['resourceBindingInfo']
        return (
            resource_binding_info['boundResourceCount'],
            resource_binding_info['onlineBoundResourceCount'],
            )

    wait_for_equal(_get_resource_count, expected_resource_count, args=(api, plugin_name))


def _test_bound_resource_count(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    camera_count = 2
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    two_mediaservers.setup_system()
    two_mediaservers.merge()
    server_1 = two_mediaservers.first.installation()
    server_2 = two_mediaservers.second.installation()
    server_1.api.set_license_server(license_server.url())
    server_1.allow_license_server_access(license_server.url())
    brand = server_1.api.get_brand()
    key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 10})
    server_1.api.activate_license(key)
    cameras_1 = add_cameras(server_1, camera_server, range(0, camera_count))
    cameras_2 = add_cameras(server_2, camera_server, range(camera_count, camera_count * 2))
    camera_ids_1 = [cam.id for cam in cameras_1]
    camera_ids_2 = [cam.id for cam in cameras_2]
    server_1.stop()
    server_2.stop()
    server_1.enable_optional_plugins(['stub'])
    server_2.enable_optional_plugins(['sample'])
    server_1.start()
    server_2.start()
    engine_collection_1 = server_1.api.get_analytics_engine_collection()
    engine_collection_2 = server_2.api.get_analytics_engine_collection()
    with camera_server.async_serve():
        video_frames_engine = engine_collection_1.get_stub('Video Frames')
        sample_engine = engine_collection_2.get_by_exact_name('Sample')
        _start_recording(server_1.api, camera_ids_1)
        for camera_id in camera_ids_1:
            server_1.api.wait_for_camera_status(camera_id, CameraStatus.RECORDING)
            server_1.api.enable_device_agent(video_frames_engine, camera_id)
        # server_2 has no cameras and no DeviceAgents when server_1 is checked
        _check_resource_count(
            server_1.api,
            video_frames_engine.name(),
            (camera_count, camera_count))
        _start_recording(server_2.api, camera_ids_2)
        for camera_id in camera_ids_2:
            server_2.api.wait_for_camera_status(camera_id, CameraStatus.RECORDING)
            server_2.api.enable_device_agent(sample_engine, camera_id)
        _check_resource_count(
            server_2.api,
            sample_engine.name(),
            (camera_count, camera_count))
    # Serving stops
    for camera_id in camera_ids_1:
        server_1.api.wait_for_camera_status(camera_id, CameraStatus.OFFLINE)
    for camera_id in camera_ids_2:
        server_2.api.wait_for_camera_status(camera_id, CameraStatus.OFFLINE)
    _check_resource_count(
        server_1.api,
        video_frames_engine.name(),
        (camera_count, 0))
    _check_resource_count(
        server_2.api,
        sample_engine.name(),
        (camera_count, 0))


def _start_recording(api, camera_ids):
    started_at = time.monotonic()
    while True:
        try:
            api.start_recording(*camera_ids)
        except RecordingStartFailed:
            _logger.debug(
                "Failed to start recording; probably servers haven't shared licenses yet")
        else:
            return
        if time.monotonic() - started_at > 5:
            raise TimeoutError("Timed out waiting for server to start recording")
        time.sleep(0.5)


_logger = logging.getLogger(__name__)
