# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras


def _test_iscsi(distrib_url, mediaserver_os, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    vm_and_mediaserver_vm_network = exit_stack.enter_context(pool.vm_and_mediaserver_vm_network(('ubuntu22', mediaserver_os)))
    [[iscsi_address, _, iscsi_machine], mediaserver_unit] = vm_and_mediaserver_vm_network
    target_iqn = iscsi_machine.os_access.create_iscsi_target(20 * 1000**3, 'test')
    mediaserver = mediaserver_unit.installation()
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    camera_server = MultiPartJpegCameraServer()
    api = mediaserver.api
    os = mediaserver.os_access
    [camera] = add_cameras(mediaserver, camera_server)
    [default_storage] = api.list_storages()
    api.disable_storage(default_storage.id)
    disk_path = os.mount_iscsi_disk(iscsi_address, target_iqn)
    api.set_up_new_storage(disk_path)
    record_from_cameras(api, [camera], camera_server, 10)
    periods_before = api.list_recorded_periods([camera.id])
    assert periods_before
    os.dismount_iscsi_disk(target_iqn)
    api.rebuild_main_archive()
    [periods_after] = api.list_recorded_periods([camera.id])
    assert not periods_after
