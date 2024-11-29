# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from mediaserver_scenarios.storage_preparation import create_smb_share


def _test_backup_to_nas(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    vm_and_mediaserver_vm_network = exit_stack.enter_context(pool.vm_and_mediaserver_vm_network(two_vm_types))
    [[smb_address, _, smb_machine], mediaserver_unit] = vm_and_mediaserver_vm_network
    mediaserver = mediaserver_unit.installation()
    mediaserver.allow_license_server_access(license_server.url())
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    brand = mediaserver.api.get_brand()
    key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 100})
    mediaserver.api.activate_license(key)
    api = mediaserver.api
    default_archive = mediaserver.default_archive()

    # Since shares are reused in tests and Windows doesn't delete SMB connections,
    # it's necessary to use different SMB shares for positive and negative tests.
    user = 'UserWithPassword'
    password = 'GoodPassword'
    [share_name, _] = create_smb_share(smb_machine.os_access, user, password, 300 * 1024**3, 'P')
    api.add_smb_storage(smb_address, share_name, user, password, is_backup=True)
    [camera] = add_cameras(mediaserver, camera_server)
    [time_period_main_before] = record_from_cameras(
        api, [camera], camera_server, duration_sec=20)
    api.enable_backup_for_cameras([camera.id])
    api.wait_for_backup_finish()

    default_archive.camera_archive(camera.physical_id).remove()
    api.rebuild_main_archive()
    [[time_period_backup_after]] = api.list_recorded_periods([camera.id])

    assert time_period_main_before == time_period_backup_after
