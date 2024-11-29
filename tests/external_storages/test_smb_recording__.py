# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.external_storages.smb_stand import smb_stand


def _test_record_on_remote(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    camera_server = MultiPartJpegCameraServer()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    stand = smb_stand(two_vm_types, pool, exit_stack)
    api = stand.mediaserver().api
    api.set_system_settings({'licenseServer': license_server.url()})
    grant_license(stand.mediaserver(), license_server)
    cameras = add_cameras(stand.mediaserver(), camera_server, indices=range(5))
    camera_ids = [camera.id for camera in cameras]
    [default_storage] = api.list_storages()
    smb_storage_id = stand.add_storage()
    api.disable_storage(default_storage.id)
    record_from_cameras(api, cameras, camera_server, 10)
    periods_before = api.list_recorded_periods(camera_ids)
    assert periods_before
    api.remove_storage(smb_storage_id)
    api.rebuild_main_archive()
    periods_after = api.list_recorded_periods(camera_ids)
    assert all(not periods_for_camera for periods_for_camera in periods_after)
