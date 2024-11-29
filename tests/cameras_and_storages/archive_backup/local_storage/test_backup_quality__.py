# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import TimePeriod
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage


def _test_backup_quality(distrib_url, one_vm_type, api_version, exit_stack):
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

    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_secondary_stream(camera.id)
    [camera_physical_id] = [camera.physical_id for camera in api.list_cameras()]
    api.enable_backup_for_cameras([camera.id])

    api.set_backup_quality_for_newly_added_cameras(low=True, high=False)
    [first_period] = record_from_cameras(
        mediaserver.api, [camera], camera_server, 20)
    api.wait_for_backup_finish()
    camera_archive = backup_archive.camera_archive(camera_physical_id)
    storage_periods_low = camera_archive.low().list_periods()
    storage_periods_high = camera_archive.high().list_periods()
    storage_periods_low = TimePeriod.consolidate(storage_periods_low, tolerance_sec=1)
    assert first_period.is_among(storage_periods_low)
    assert not first_period.is_among(storage_periods_high)

    api.set_backup_quality_for_newly_added_cameras(low=True, high=True)
    [second_period] = record_from_cameras(
        mediaserver.api, [camera], camera_server, 20)
    api.wait_for_backup_finish()
    storage_periods_low = camera_archive.low().list_periods()
    storage_periods_high = camera_archive.high().list_periods()
    storage_periods_low = TimePeriod.consolidate(storage_periods_low, tolerance_sec=2)
    storage_periods_high = TimePeriod.consolidate(storage_periods_high, tolerance_sec=2)
    assert first_period.is_among(storage_periods_low, tolerance_sec=2)
    assert first_period.is_among(storage_periods_high, tolerance_sec=2)
    assert second_period.is_among(storage_periods_low, tolerance_sec=2)
    assert second_period.is_among(storage_periods_high, tolerance_sec=2)
