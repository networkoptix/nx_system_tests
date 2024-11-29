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


def _test_storage_failover_on_space_issue(distrib_url, two_vm_types, api_version, exit_stack):
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
    camera = discover_camera(one, camera_server, '/test.mjpeg')
    one.api.set_camera_preferred_parent(camera.id, one.api.get_server_id())
    [one_storage] = one.api.list_storages()
    assert one_storage.free_space > one_storage.reserved_space
    # Reserve all free space on the first storage
    one.api.reserve_storage_space(one_storage.id, one_storage.free_space)
    two.api.enable_failover(max_cameras=1)
    [camera] = advertise_to_change_camera_parent([camera], [one, two])
    assert camera.parent_id == two.api.get_server_id()
