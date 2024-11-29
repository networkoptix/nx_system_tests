# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math
import time
from datetime import datetime
from datetime import timedelta

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
from tests.cameras_and_storages.archive_backup.local_storage.common import wait_before_expected_backup_time
from tests.cameras_and_storages.archive_backup.local_storage.common import wait_for_backup_started


def _test_limit_bandwidth_by_schedule(distrib_url, one_vm_type, api_version, exit_stack):
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
    vm_control = one_mediaserver.vm().vm_control
    storage = add_backup_storage(mediaserver, vm_control, 'V', 20_000)
    backup_archive = mediaserver.archive(storage.path)

    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_secondary_stream(camera.id)
    record_from_cameras(api, [camera], camera_server, 30)

    bandwidth_limit_bps = 1000**2 // 8
    server_time = api.get_datetime()
    timezone = mediaserver.os_access.get_datetime().tzinfo
    backup_start_time_expected = datetime(
        server_time.year, server_time.month, server_time.day, 12, 00, tzinfo=timezone)
    api.limit_backup_bandwidth_by_schedule(
        day=backup_start_time_expected.strftime('%A'),
        hour=backup_start_time_expected.hour,
        bytes_per_sec=bandwidth_limit_bps)

    mediaserver.stop()
    server_time_shift_sec = 60
    mediaserver.os_access.set_datetime(
        backup_start_time_expected - timedelta(seconds=server_time_shift_sec))
    mediaserver.start()

    expected_backup_start_timestamp = backup_start_time_expected.timestamp()
    api.enable_backup_for_cameras([camera.id])
    wait_before_expected_backup_time(
        api, camera.id, backup_archive, expected_backup_start_timestamp)
    wait_for_backup_started(api, camera.id, backup_archive)

    # Wait for stabilization of backup speed.
    stabilization_period_sec = 10
    time.sleep(stabilization_period_sec)
    initial_backup_archive_size = backup_archive.camera_archive(camera.physical_id).size_bytes()
    backup_working_period_sec = 45
    # Wait for an opportunity to estimate average speed.
    time.sleep(backup_working_period_sec)
    updated_backup_archive_size = backup_archive.camera_archive(camera.physical_id).size_bytes()
    assert initial_backup_archive_size < updated_backup_archive_size

    main_archive_size = mediaserver.default_archive().camera_archive(camera.physical_id).size_bytes()
    assert updated_backup_archive_size < main_archive_size

    backup_archive_size_diff = updated_backup_archive_size - initial_backup_archive_size
    actual_bandwidth_bps = backup_archive_size_diff / backup_working_period_sec
    assert math.isclose(actual_bandwidth_bps, bandwidth_limit_bps, rel_tol=0.1)
