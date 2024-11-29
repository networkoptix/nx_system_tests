# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.storage_preparation import add_smb_storage


def _test_nas_reserved_space_with_quota_enabled(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    vm_and_mediaserver_vm_network = exit_stack.enter_context(pool.vm_and_mediaserver_vm_network(two_vm_types))
    [[smb_ip, _, smb_machine], mediaserver_unit] = vm_and_mediaserver_vm_network
    mediaserver = mediaserver_unit.installation()
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    api = mediaserver.api
    disk_size = int(1.2 * 1024**4)

    small = add_smb_storage(
        api, smb_machine.os_access, str(smb_ip), disk_size, quota=300 * 1024**3)
    medium = add_smb_storage(
        api, smb_machine.os_access, str(smb_ip), disk_size, quota=512 * 1024**3)
    large = add_smb_storage(
        api, smb_machine.os_access, str(smb_ip), disk_size, quota=1100 * 1024**3)

    storages = api.list_storages()
    [storage_s] = [s for s in storages if s.id == small.id]
    [storage_m] = [s for s in storages if s.id == medium.id]
    [storage_l] = [s for s in storages if s.id == large.id]

    expected_s = 50 * 1024**3
    assert storage_s.reserved_space == expected_s, (
        f"Expected reserved space: {expected_s}; got: {storage_s.reserved_space}")
    expected_m = int(storage_m.space * 0.1)
    assert storage_m.reserved_space == expected_m, (
        f"Expected reserved space: {expected_m}; got: {storage_m.reserved_space}")
    # VMS-52446: 30-percent upper bound removed
    expected_l = int(storage_l.space * 0.1)
    assert storage_l.reserved_space == expected_l, (
        f"Expected reserved space: {expected_l}; got: {storage_l.reserved_space}")
