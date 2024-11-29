# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from os_access import WindowsAccess
from tests.waiting import wait_for_truthy


def _test_license_expiration_during_failover_period(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    if isinstance(one.os_access, WindowsAccess):
        one.os_access.disable_netprofm_service()
    if isinstance(two.os_access, WindowsAccess):
        two.os_access.disable_netprofm_service()
    for mediaserver in one, two:
        # forceStopRecordingTime in seconds since mediaserver 4.0.
        mediaserver.update_conf({'forceStopRecordingTime': 1})
        # Set the license check interval to 500 ms to speed up tests.
        mediaserver.update_ini('nx_vms_server', {'checkLicenseIntervalMs': 500})
        mediaserver.start()
        mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    merge_systems(one, two, take_remote_settings=False)
    camera_server = MultiPartJpegCameraServer()
    [camera] = add_cameras(two, camera_server)
    brand = one.api.get_brand()
    new_key = license_server.generate({'BRAND2': brand})
    one.allow_license_server_access(license_server.url())
    one.api.activate_license(new_key)
    wait_for_truthy(two.api.list_licenses)
    two.api.start_recording(camera.id)
    assert two.api.recording_is_enabled(camera.id)
    one.stop()
    wait_for_truthy(
        lambda: not two.api.recording_is_enabled(camera.id),
        description="Recording disabled",
        )
