# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from mediaserver_scenarios.storage_preparation import add_smb_storage
from tests.external_storages.smb_stand import smb_stand
from tests.waiting import wait_for_truthy


def _test_share_with_quota(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    camera_server = MultiPartJpegCameraServer()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    stand = smb_stand(two_vm_types, pool, exit_stack)
    api = stand.mediaserver().api
    [default_storage] = api.list_storages()
    username = 'UserWithPassword'
    password = 'GoodPassword'
    smb_share = add_smb_storage(
        mediaserver_api=api,
        smb_server_os_access=stand.smb_os_access(),
        smb_server_host=stand.smb_address(),
        storage_size_bytes=200 * 1024**3,
        quota=100 * 1024**3,
        user=username,
        password=password,
        )
    api.disable_storage(default_storage.id)
    [smb_storage] = api.list_storages(within_path=smb_share.url)
    assert smb_storage.type == 'smb'
    assert smb_storage.is_enabled is True
    api.set_system_settings({'licenseServer': license_server.url()})
    grant_license(stand.mediaserver(), license_server)
    [camera] = add_cameras(stand.mediaserver(), camera_server)
    [time_period] = record_from_cameras(api, [camera], camera_server, 10)
    api.remove_storage(smb_storage.id)
    api.rebuild_main_archive()
    [periods] = api.list_recorded_periods([camera.id])
    assert not periods
    [*_, address, share] = smb_share.url.split('/')
    api.add_smb_storage(address, share, username, password)
    wait_for_truthy(_time_period_present, args=[api, camera.id, time_period])


def _time_period_present(api, camera_id, time_period):
    [periods] = api.list_recorded_periods([camera_id])
    return time_period in periods
