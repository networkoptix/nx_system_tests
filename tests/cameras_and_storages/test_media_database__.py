# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras


def _test_restore_corrupted_db(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.start()
    mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
    grant_license(mediaserver, license_server)
    [camera] = add_cameras(mediaserver, camera_server)
    record_from_cameras(
        mediaserver.api, [camera], camera_server, duration_sec=20)
    [[period_before]] = mediaserver.api.list_recorded_periods(
        [camera.id], incomplete_ok=False)
    [storage] = mediaserver.api.list_storages()
    mediaserver.stop()
    nxdb = mediaserver.nxdb(storage.path)
    [db_path_relative] = nxdb.list_files()
    db_path = storage.path / db_path_relative
    db_size = mediaserver.os_access.path(db_path).size()
    valid_db_md5 = mediaserver.os_access.file_md5(db_path)
    with mediaserver.os_access.path(db_path).open('rb+') as f:
        f.seek(int(db_size / 2))
        f.write(b'corrupt')
    corrupted_db_md5 = mediaserver.os_access.file_md5(db_path)
    assert valid_db_md5 != corrupted_db_md5
    mediaserver.start()
    [[period_after]] = mediaserver.api.list_recorded_periods(
        [camera.id], incomplete_ok=False, empty_ok=False)
    assert period_before == period_after
