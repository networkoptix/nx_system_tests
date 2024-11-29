# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_many_servers
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.merged_systems.failover.conftest import advertise_to_change_camera_parent
from tests.merged_systems.failover.conftest import discover_camera


def _test_storage_failover(distrib_url, two_vm_types, api_version, exit_stack):
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
        server.allow_license_server_access(license_server.url())
        brand = server.api.get_brand()
        key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 100})
        server.api.activate_license(key)
    merge_many_servers([one, two])
    camera_server = MultiPartJpegCameraServer()
    dummy_smb_storage_id = one.api.add_dummy_smb_storage(index=1)
    one.api.enable_failover(max_cameras=2)
    two.api.enable_failover(max_cameras=2)
    [one_guid, two_guid] = [one.api.get_server_id(), two.api.get_server_id()]
    camera_1 = discover_camera(one, camera_server, '/test1.mjpeg')
    camera_2 = discover_camera(two, camera_server, '/test2.mjpeg')
    one.api.set_camera_preferred_parent(camera_1.id, one_guid)
    two.api.set_camera_preferred_parent(camera_2.id, two_guid)
    # Disable storages on the second server
    [two_storage] = two.api.list_storages()
    two.api.disable_storage(two_storage.id)
    [camera_2] = advertise_to_change_camera_parent([camera_2], [one, two])
    assert camera_2.parent_id == one_guid
    # Enable storages on the second server
    two.api.enable_storage(two_storage.id)
    # Make all non-system storages backup on the first server
    one.api.request_allocate_storage_for_backup(dummy_smb_storage_id)
    # Disable system storage on the first server.
    [one_storage] = one.api.list_storages(ignore_offline=True, storage_type='local')
    one.api.disable_storage(one_storage.id)
    [camera_1, camera_2] = advertise_to_change_camera_parent(
        [camera_1, camera_2], [one, two])
    assert camera_2.parent_id == two_guid
    assert camera_1.parent_id == two_guid
