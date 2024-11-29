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


def _test_failover_and_auto_discovery(distrib_url, api_version, two_vm_types, discovery, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    two_mediaservers = exit_stack.enter_context(pool.two_mediaservers(two_vm_types))
    two_mediaservers.start()
    one = two_mediaservers.first.installation()
    two = two_mediaservers.second.installation()
    one.api.setup_local_system({'licenseServer': license_server.url()})
    configure_license(one, license_server)
    two.api.setup_local_system({
        'autoDiscoveryEnabled': discovery, 'licenseServer': license_server.url()})
    one_guid, two_guid = one.api.get_server_id(), two.api.get_server_id()
    camera_1 = discover_camera(one, camera_server, '/test1.mjpeg')
    one.api.set_camera_preferred_parent(camera_1.id, one_guid)
    camera_2 = discover_camera(one, camera_server, '/test2.mjpeg')
    one.api.set_camera_preferred_parent(camera_2.id, one_guid)
    two.api.enable_failover(max_cameras=2)
    merge_many_servers([one, two])
    one_guid = one.api.get_server_id()
    two_guid = two.api.get_server_id()
    one.stop()
    [camera_1] = advertise_to_change_camera_parent([camera_1], [two])
    assert camera_1.parent_id == two_guid
    [camera_2] = advertise_to_change_camera_parent([camera_2], [two])
    assert camera_2.parent_id == two_guid
    one.start()
    [camera_1, camera_2] = advertise_to_change_camera_parent([camera_1, camera_2], [one, two])
    assert camera_1.parent_id == one_guid
    assert camera_2.parent_id == one_guid
