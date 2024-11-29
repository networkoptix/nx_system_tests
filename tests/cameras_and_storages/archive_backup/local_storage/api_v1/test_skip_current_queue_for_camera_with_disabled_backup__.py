# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_api import MediaserverApiV1
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage
from tests.cameras_and_storages.archive_backup.local_storage.common import backup_archive_size_is_enough
from tests.waiting import wait_for_truthy


def _test_skip_current_queue_for_camera_with_disabled_backup(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    license_server = LocalLicenseServer()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({'mediaFileDuration': 1})
    mediaserver.start(already_started_ok=True)
    api: MediaserverApiV1 = mediaserver.api
    with license_server.serving():
        api.setup_local_system({'licenseServer': license_server.url()}, basic_and_digest_auth_required=False)
        grant_license(mediaserver, license_server)
    storage = add_backup_storage(one_mediaserver.mediaserver(), one_mediaserver.vm().vm_control, 'V', 20_000)
    backup_archive = one_mediaserver.mediaserver().archive(storage.path)

    [camera_one, camera_two] = add_cameras(mediaserver, camera_server, indices=(0, 1))
    api.enable_secondary_stream(camera_one.id)
    api.enable_secondary_stream(camera_two.id)
    [camera_one_period_before, camera_two_period_before] = record_from_cameras(
        api, [camera_one, camera_two], camera_server, duration_sec=15)

    api.limit_backup_bandwidth(bytes_per_sec=125 * 1000)
    api.set_backup_quality_for_newly_added_cameras(low=True, high=True)
    api.set_backup_all_archive(camera_one.id)
    api.set_backup_all_archive(camera_two.id)
    api.enable_backup_for_cameras([camera_two.id])
    enough_size = 16 * 1024
    wait_for_truthy(
        backup_archive_size_is_enough, args=[backup_archive, camera_two.physical_id, enough_size])
    api.skip_all_backup_queues()
    [camera_one_period_after] = record_from_cameras(
        api, [camera_one], camera_server, duration_sec=15)
    api.set_unlimited_backup_bandwidth()
    api.enable_backup_for_cameras([camera_one.id])
    api.wait_for_backup_finish()

    camera_one_backup_archive = backup_archive.camera_archive(camera_one.physical_id)
    camera_two_backup_archive = backup_archive.camera_archive(camera_two.physical_id)
    camera_one_backup_low = camera_one_backup_archive.low().list_periods()
    camera_one_backup_high = camera_one_backup_archive.high().list_periods()
    camera_two_backup_low = camera_two_backup_archive.low().list_periods()
    camera_two_backup_high = camera_two_backup_archive.high().list_periods()

    assert not camera_one_period_before.is_among(camera_one_backup_low)
    assert not camera_one_period_before.is_among(camera_one_backup_high)
    assert not camera_two_period_before.is_among(camera_two_backup_low)
    assert not camera_two_period_before.is_among(camera_two_backup_high)
    assert camera_one_period_after.is_among(camera_one_backup_low)
    assert camera_one_period_after.is_among(camera_one_backup_high)
