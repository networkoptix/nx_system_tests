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


def _test_backup_modes(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
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
    camera_server = MultiPartJpegCameraServer()

    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_secondary_stream(camera.id)

    # Test real-time mode (for live video)
    api.enable_backup_for_cameras([camera.id])
    [time_period] = record_from_cameras(api, [camera], camera_server, 10)
    api.wait_for_backup_finish()
    backup_camera_archive = backup_archive.camera_archive(camera.physical_id)
    archive_periods_low = backup_camera_archive.low().list_periods()
    archive_periods_high = backup_camera_archive.high().list_periods()
    assert time_period.is_among(archive_periods_low)
    assert time_period.is_among(archive_periods_high)

    # Test offline mode (for backing up already early recorded archive)
    api.disable_backup_for_cameras([camera.id])
    [time_period] = record_from_cameras(api, [camera], camera_server, 10)
    api.enable_backup_for_cameras([camera.id])
    api.wait_for_backup_finish()
    archive_periods_low = backup_camera_archive.low().list_periods()
    archive_periods_high = backup_camera_archive.high().list_periods()
    assert time_period.is_among(archive_periods_low)
    assert time_period.is_among(archive_periods_high)
