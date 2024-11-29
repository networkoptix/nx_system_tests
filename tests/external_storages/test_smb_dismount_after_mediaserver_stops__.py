# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import StorageUnavailable
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.external_storages.smb_stand import smb_stand
from tests.infra import assert_raises


def _test_dismount_nas_after_server_stopped(distrib_url, two_vm_types, api_version, recording_enabled_before_restart, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    camera_server = MultiPartJpegCameraServer()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    stand = smb_stand(two_vm_types, pool, exit_stack)
    api = stand.mediaserver().api
    os = stand.mediaserver().os_access
    api.set_system_settings({'licenseServer': license_server.url()})
    grant_license(stand.mediaserver(), license_server)
    # Set minimal sample duration to make this test faster.
    stand.mediaserver().update_conf({'mediaFileDuration': 1})
    stand.mediaserver().stop()
    stand.mediaserver().start()
    [default_storage] = api.list_storages()
    api.disable_storage(default_storage.id)
    mount_point = os.path('/media/smb/')
    mount_point.rmtree(ignore_errors=True)
    stand.mount(mount_point)
    [_, saved_storage] = api.set_up_new_storage(mount_point)
    archive = stand.mediaserver().archive(saved_storage.path)
    [camera] = add_cameras(stand.mediaserver(), camera_server)
    if recording_enabled_before_restart:
        api.start_recording(camera.id, no_storages_ok=True)
        camera_server.serve(10)
    stand.mediaserver().stop()
    os.dismount_smb_share(mount_point, lazy=False)
    stand.mediaserver().start()
    if not recording_enabled_before_restart:
        api.start_recording(camera.id, no_storages_ok=True)
    camera_server.serve(10)
    with assert_raises(StorageUnavailable):
        api.list_storages(archive.storage_root_path())
    server_nxdb = stand.mediaserver().nxdb(saved_storage.path)
    assert not server_nxdb.exists()
    assert not archive.has_mkv_files()
