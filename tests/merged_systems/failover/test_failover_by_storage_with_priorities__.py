# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_many_servers
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.merged_systems.failover.conftest import advertise_to_change_camera_parent
from tests.merged_systems.failover.conftest import configure_license
from tests.merged_systems.failover.conftest import discover_camera


def _test_storage_failover_with_camera_priorities(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    for server in one, two:
        server.api.setup_local_system({'licenseServer': license_server.url()})
        configure_license(server, license_server)
    merge_many_servers([one, two])
    camera_server = MultiPartJpegCameraServer()
    [one_guid, two_guid] = [one.api.get_server_id(), two.api.get_server_id()]
    one_cameras = []
    for priority in ['High', 'Medium', 'Low', 'Never']:
        camera = discover_camera(one, camera_server, f'/test_{priority}.mjpeg')
        one_cameras.append(camera)
        one.api.set_camera_preferred_parent(camera.id, one_guid)
        one.api.set_camera_failover_priority(camera.id, priority)
    [camera_high, camera_medium, camera_low, camera_never] = one_cameras
    [one_storage] = one.api.list_storages()
    one.api.disable_storage(one_storage.id)
    two.api.enable_failover(max_cameras=1)
    [camera_high] = advertise_to_change_camera_parent(
        [camera_high], [one, two], advertising_cameras=one_cameras)
    assert camera_high.parent_id == two_guid
    two.api.enable_failover(max_cameras=2)
    [camera_medium] = advertise_to_change_camera_parent(
        [camera_medium], [one, two], advertising_cameras=one_cameras)
    assert camera_medium.parent_id == two_guid
    two.api.enable_failover(max_cameras=3)
    [camera_low] = advertise_to_change_camera_parent(
        [camera_low], [one, two], advertising_cameras=one_cameras)
    assert camera_low.parent_id == two_guid
    two.api.enable_failover(max_cameras=4)
    [camera_never] = advertise_to_change_camera_parent(
        [camera_never], [one, two], timeout_sec=30)
    assert camera_never.parent_id == one_guid
