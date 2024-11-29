# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from os_access import DeviceBusyError
from tests.external_storages.smb_stand import smb_stand
from tests.infra import assert_raises


def _test_dismount_nas_while_server_is_working(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    camera_server = MultiPartJpegCameraServer()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    stand = smb_stand(two_vm_types, pool, exit_stack)
    api = stand.mediaserver().api
    os = stand.mediaserver().os_access
    mount_point = os.path('/media/smb/')
    [default_storage] = api.list_storages()
    api.disable_storage(default_storage.id)
    stand.mount(mount_point)
    api.set_up_new_storage(mount_point)
    api.set_system_settings({'licenseServer': license_server.url()})
    grant_license(stand.mediaserver(), license_server)
    [camera] = add_cameras(stand.mediaserver(), camera_server)
    api.start_recording(camera.id)
    with assert_raises(DeviceBusyError):
        os.dismount_smb_share(mount_point, lazy=False)
