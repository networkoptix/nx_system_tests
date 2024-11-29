# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from mediaserver_scenarios.storage_preparation import create_smb_share


def _test_nas_archive_after_rebuild(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    vm_and_mediaserver_vm_network = exit_stack.enter_context(pool.vm_and_mediaserver_vm_network(two_vm_types))
    [[smb_address, _, smb_machine], mediaserver_unit] = vm_and_mediaserver_vm_network
    mediaserver = mediaserver_unit.installation()
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    user = 'UserWithPassword'
    password = 'GoodPassword'
    api = mediaserver.api
    os = mediaserver.os_access
    [default_storage] = api.list_storages()
    [camera] = add_cameras(mediaserver, camera_server)
    disk_size = int(300 * 1024**3)
    share_name, _ = create_smb_share(smb_machine.os_access, user, password, disk_size, 'S')
    mount_point = os.path('/media/smb/')
    os.mount_smb_share(
        mount_point=mount_point,
        path=f'//{smb_address}/{share_name}',
        username=user,
        password=password,
        )
    api.disable_storage(default_storage.id)
    [_, saved_storage] = api.set_up_new_storage(mount_point)
    record_from_cameras(api, [camera], camera_server, 60)
    mediaserver.stop()
    server_nxdb = mediaserver.nxdb(saved_storage.path)
    server_nxdb.remove()
    mediaserver.start()
    assert api.list_recorded_periods([camera.id])
