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


def _test_limit_bandwidth(distrib_url, one_vm_type, bandwidth_limit_multiplier, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    camera_server = MultiPartJpegCameraServer()
    license_server = LocalLicenseServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
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
    record_length_sec = bandwidth_limit_multiplier * 30
    record_from_cameras(api, [camera], camera_server, record_length_sec)

    bandwidth_limit_bps = bandwidth_limit_multiplier * 1000**2 // 8
    api.limit_backup_bandwidth(bytes_per_sec=bandwidth_limit_bps)
    api.enable_backup_for_cameras([camera.id])

    # Wait for stabilization of backup speed
    stabilization_period_sec = 10
    time.sleep(stabilization_period_sec)

    camera_backup_archive = backup_archive.camera_archive(camera.physical_id)
    initial_backup_archive_size = camera_backup_archive.size_bytes()
    backup_working_period_sec = 45
    # Wait for some amount of data to be backed up
    time.sleep(backup_working_period_sec)
    updated_backup_archive_size = camera_backup_archive.size_bytes()
    assert initial_backup_archive_size < updated_backup_archive_size

    main_archive_size = mediaserver.default_archive().camera_archive(camera.physical_id).size_bytes()
    assert updated_backup_archive_size < main_archive_size

    backup_archive_size_diff = updated_backup_archive_size - initial_backup_archive_size
    actual_bandwidth_bps = backup_archive_size_diff / backup_working_period_sec
    assert math.isclose(actual_bandwidth_bps, bandwidth_limit_bps, rel_tol=0.1)
