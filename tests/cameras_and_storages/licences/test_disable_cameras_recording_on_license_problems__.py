# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from ipaddress import ip_network
from typing import Iterable
from typing import Mapping

from directories import get_run_dir
from doubles.licensing import LicenseServer
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from mediaserver_api import BaseCamera
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from os_access import WindowsAccess
from tests.waiting import wait_for_equal

_logger = logging.getLogger(__name__)


def _test_disable_cameras_recording_on_license_problems(
        distrib_url,
        three_vm_types,
        api_version,
        cameras_count,
        licenses_count,
        expected_count,
        exit_stack,
        ):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    [first_vm_type, second_vm_type, third_vm_type] = three_vm_types
    test_network = ip_network('10.254.1.0/24')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    network_and_system = exit_stack.enter_context(pool.system({
        'machines': [
            {'alias': 'first', 'type': first_vm_type},
            {'alias': 'second', 'type': second_vm_type},
            {'alias': 'third', 'type': third_vm_type},
            ],
        'networks': {
            str(test_network): {
                'first': None,
                'second': None,
                'third': None,
                },
            },
        'mergers': [
            dict(local='first', remote='second', take_remote_settings=False, network=test_network),
            dict(local='first', remote='third', take_remote_settings=False, network=test_network),
            ],
        }))
    [system, machines, assignments] = network_and_system
    for vm in machines.values():
        if isinstance(vm.os_access, WindowsAccess):
            vm.os_access.disable_netprofm_service()
    [first_server, second_server, third_server] = _three_prepared_mediaservers(
        system, license_server)
    first_cameras = add_cameras(first_server, camera_server, range(100, 104))
    [second_camera] = add_cameras(second_server, camera_server, (200,))
    third_cameras = add_cameras(third_server, camera_server, range(300, 300 + cameras_count))
    brand = first_server.api.get_brand()
    key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 30})
    first_server.api.activate_license(key)
    for camera in first_cameras:
        first_server.api.start_recording(camera.id)
    second_server.api.start_recording(second_camera.id)
    brand = third_server.api.get_brand()
    key = license_server.generate({'BRAND2': brand, 'QUANTITY2': licenses_count})
    third_server.api.activate_license(key)
    for camera in third_cameras:
        third_server.api.start_recording(camera.id)
    assert second_server.api.recording_is_enabled(second_camera.id)
    assert _count_recording_cameras(third_server, third_cameras) == cameras_count

    def count_recording_cameras() -> int:
        second_count = _count_recording_cameras(second_server, [second_camera])
        third_count = _count_recording_cameras(third_server, third_cameras)
        _logger.info(
            "Second server: %s cameras, third server: %s cameras",
            second_count, third_count)
        return second_count + third_count

    first_vm = machines['first']
    [_, first_nic] = assignments['first'][test_network]
    first_vm.vm_control.disconnect_cable(first_nic)
    wait_for_equal(count_recording_cameras, expected_count, timeout_sec=180)
    for camera in first_cameras:
        if not first_server.api.recording_is_enabled(camera.id):
            raise RuntimeError(
                f"Camera {camera.id} on the first server is not recording")
    first_vm.vm_control.connect_cable(first_nic)
    [third_ip, _] = assignments['third'][test_network]
    first_server.os_access.networking.ping(str(third_ip))
    for camera in first_cameras:
        if not first_server.api.recording_is_enabled(camera.id):
            raise RuntimeError(
                f"Camera {camera.id} on the first server is not recording")
    assert count_recording_cameras() == expected_count


def _three_prepared_mediaservers(systems: Mapping[str, Mediaserver], license_server: LicenseServer):
    for mediaserver in (systems['first'], systems['second'], systems['third']):
        # forceStopRecordingTime in seconds since mediaserver 4.0.
        mediaserver.update_conf({'forceStopRecordingTime': 1})
        # Set the license check interval to 500 ms to speed up tests.
        mediaserver.update_ini('nx_vms_server', {'checkLicenseIntervalMs': 500})
        mediaserver.api.set_license_server(license_server.url())
        mediaserver.allow_license_server_access(license_server.url())
        mediaserver.api.restart()
    return systems['first'], systems['second'], systems['third']


def _count_recording_cameras(mediaserver: Mediaserver, cameras: Iterable[BaseCamera]) -> int:
    count = 0
    for camera in cameras:
        if mediaserver.api.recording_is_enabled(camera.id):
            count += 1
    return count
