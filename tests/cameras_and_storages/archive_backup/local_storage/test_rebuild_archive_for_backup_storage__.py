# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.license_scenarios import grant_license
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from tests.cameras_and_storages.archive_backup.local_storage.common import add_backup_storage
from tests.waiting import wait_for_truthy

_logger = logging.getLogger(__name__)


def _test_rebuild_archive_for_backup_storage(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    license_server = LocalLicenseServer()
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.update_conf({'mediaFileDuration': 1})
    mediaserver.start(already_started_ok=True)
    with license_server.serving():
        mediaserver.api.setup_local_system({'licenseServer': license_server.url()})
        grant_license(mediaserver, license_server)
    storage = add_backup_storage(one_mediaserver.mediaserver(), one_mediaserver.vm().vm_control, 'V', 20_000)
    backup_archive = one_mediaserver.mediaserver().archive(storage.path)
    [camera] = add_cameras(mediaserver, camera_server)
    mediaserver.api.enable_secondary_stream(camera.id)
    [period_before] = record_from_cameras(
        mediaserver.api, [camera], camera_server, duration_sec=20)
    mediaserver.api.enable_backup_for_cameras([camera.id])
    mediaserver.api.wait_for_backup_finish()
    main_archive = mediaserver.default_archive()
    camera_id = camera.physical_id
    tolerance_ms = 500
    main_camera_archive = main_archive.camera_archive(camera_id)
    backup_camera_archive = backup_archive.camera_archive(camera_id)
    [main_low_res_period] = main_camera_archive.low().list_periods()
    [main_hi_res_period] = main_camera_archive.high().list_periods()
    [backup_low_res_period] = backup_camera_archive.low().list_periods()
    [backup_hi_res_period] = backup_camera_archive.high().list_periods()
    assert backup_low_res_period.contains(main_low_res_period.trim_right(tolerance_ms))
    assert backup_hi_res_period.contains(main_hi_res_period.trim_right(tolerance_ms))

    mediaserver.stop()
    nxdb = one_mediaserver.mediaserver().nxdb(storage.path)
    nxdb.remove()
    tmp_main_archive = main_archive.with_name('tmp')
    tmp_backup_archive = backup_archive.with_name('tmp')
    main_archive.exchange_contents(tmp_main_archive)
    backup_archive.exchange_contents(tmp_backup_archive)
    mediaserver.start()
    time.sleep(15)
    [[]] = mediaserver.api.list_recorded_periods([camera.id], empty_ok=True)
    mediaserver.stop()
    assert not backup_archive.has_mkv_files()
    backup_archive.exchange_contents(tmp_backup_archive)

    mediaserver.start()
    mediaserver.api.rebuild_backup_archive()
    wait_for_truthy(
        _period_restored,
        args=[mediaserver.api, camera.id, period_before],
        description=f"{period_before} is restored",
        timeout_sec=10)


def _period_restored(api, camera_id, expected):
    [periods] = api.list_recorded_periods([camera_id])
    if periods:
        if len(periods) != 1:
            raise AssertionError(f"Expected one period, got {periods!r}")
        [period] = periods
        # The backup process omits the last chunk if it is shorter than 500 ms.
        if period.contains(expected.trim_right(ms=500)):
            return True
    return False
