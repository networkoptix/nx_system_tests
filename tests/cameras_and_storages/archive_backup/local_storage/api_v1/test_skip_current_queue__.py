# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import math
import time

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


def _test_skip_current_queue(distrib_url, one_vm_type, api_version, exit_stack):
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

    [camera] = add_cameras(mediaserver, camera_server)
    api.enable_secondary_stream(camera.id)

    record_from_cameras(api, [camera], camera_server, 10)
    # Limit to reduce recording period which can demonstrate skipping the current queue.
    api.limit_backup_bandwidth(bytes_per_sec=125 * 1000)
    api.enable_backup_for_cameras([camera.id])
    # Wait for some amount of video is backed up.
    # 10 seconds video backs up around 25 seconds with 1M/bits limit of the bandwidth.
    time.sleep(1)
    # https://networkoptix.atlassian.net/wiki/spaces/FS/pages/1785299652#2.1.2.-Configured
    api.skip_current_backup_queue(camera.id)
    skip_current_queue_timestamp_ms = int(api.get_datetime().timestamp() * 1000)
    api.wait_for_backup_finish()

    backup_state = api.get_actual_backup_state(camera.id)
    assert math.isclose(backup_state.position.low_ms, skip_current_queue_timestamp_ms, abs_tol=1000)
    assert math.isclose(backup_state.position.high_ms, skip_current_queue_timestamp_ms, abs_tol=1000)
    assert math.isclose(backup_state.bookmark_start_position_ms, skip_current_queue_timestamp_ms, abs_tol=1000)

    default_archive = mediaserver.default_archive()
    main_camera_archive = default_archive.camera_archive(camera.physical_id)
    [low_main_period] = main_camera_archive.low().list_periods()
    [high_main_period] = main_camera_archive.high().list_periods()
    backup_camera_archive = backup_archive.camera_archive(camera.physical_id)
    [low_backup_period] = backup_camera_archive.low().list_periods()
    [high_backup_period] = backup_camera_archive.high().list_periods()

    assert low_main_period.start == low_backup_period.start
    assert low_main_period.duration_sec / low_backup_period.duration_sec > 2
    assert high_main_period.start == high_backup_period.start
    assert high_main_period.duration_sec / high_backup_period.duration_sec > 2
