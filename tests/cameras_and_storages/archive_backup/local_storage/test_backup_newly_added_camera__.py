# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage
from tests.cameras_and_storages.archive_backup.local_storage.common import archive_is_backed_up


def _test_backup_newly_added_camera(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    license_server = LocalLicenseServer()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({'mediaFileDuration': 1})
    mediaserver.start(already_started_ok=True)
    api = mediaserver.api
    with license_server.serving():
        api.setup_local_system({'licenseServer': license_server.url()}, basic_and_digest_auth_required=False)
        grant_license(mediaserver, license_server)
    storage = add_backup_storage(one_mediaserver.mediaserver(), one_mediaserver.vm().vm_control, 'V', 20_000)
    backup_archive = one_mediaserver.mediaserver().archive(storage.path)
    [camera_one] = add_cameras(mediaserver, camera_server, indices=range(0, 1))
    api.enable_secondary_stream(camera_one.id)
    api.enable_backup_for_cameras([camera_one.id])
    api.enable_backup_for_newly_added_cameras()

    [camera_two] = add_cameras(mediaserver, camera_server, indices=range(1, 2))
    api.enable_secondary_stream(camera_two.id)
    [camera_one_recorded, camera_two_recorded] = record_from_cameras(
        api, [camera_one, camera_two], camera_server, 10)
    api.wait_for_backup_finish()

    api.disable_backup_for_newly_added_cameras()

    [camera_three] = add_cameras(mediaserver, camera_server, indices=range(2, 3))
    api.enable_secondary_stream(camera_three.id)
    [camera_three_recorded] = record_from_cameras(
        api, [camera_three], camera_server, 10)
    api.wait_for_backup_finish()

    assert archive_is_backed_up(
        backup_archive.camera_archive(camera_one.physical_id), camera_one_recorded)
    assert archive_is_backed_up(
        backup_archive.camera_archive(camera_two.physical_id), camera_two_recorded)
    assert not archive_is_backed_up(
        backup_archive.camera_archive(camera_three.physical_id), camera_three_recorded)
