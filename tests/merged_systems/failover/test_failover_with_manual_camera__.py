# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_many_servers
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.merged_systems.failover.conftest import advertise_to_change_camera_parent
from tests.merged_systems.failover.conftest import configure_license


def _test_failover_for_manually_added_camera(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    for server in one, two:
        server.api.setup_local_system({
            'autoDiscoveryEnabled': 'false', 'licenseServer': license_server.url()})
    [one_guid, two_guid] = [one.api.get_server_id(), two.api.get_server_id()]
    configure_license(one, license_server)
    [camera] = add_cameras(one, camera_server)
    one.api.set_camera_preferred_parent(camera.id, one_guid)
    merge_many_servers([one, two])
    two.api.enable_failover(max_cameras=1)
    one.stop()
    # The test is passed only if the camera.manuallyAdded=false on the second server.
    # VMS-18945: Remove this when fixed.
    two.api.add_generated_camera({'id': str(camera.id), 'manuallyAdded': False})
    [camera] = advertise_to_change_camera_parent([camera], [two])
    assert camera.parent_id == two_guid
    one.start()
    [camera] = advertise_to_change_camera_parent([camera], [one, two])
    assert camera.parent_id == one_guid
