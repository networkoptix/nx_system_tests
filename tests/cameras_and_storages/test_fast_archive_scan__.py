# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timezone

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.waiting import wait_for_truthy


def _test_fast_archive_scan(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    vm = one_mediaserver.hardware()
    api = one_mediaserver.api()
    os = mediaserver.os_access
    vm.add_disk('sata', 20 * 1024)
    extra_path = os.mount_disk('E')
    [_, extra_storage] = api.set_up_new_storage(extra_path, is_backup=True)
    extra_storage_archive = mediaserver.archive(extra_storage.path)
    [camera] = api.add_test_cameras(offset=0, count=1)
    api.enable_backup_for_cameras([camera.id])
    start_time = datetime(2020, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    camera_archive = extra_storage_archive.camera_archive(camera.physical_id)
    time_period_before = camera_archive.high().add_fake_record(
        start_time=start_time,
        duration_sec=2,
        )
    mediaserver.stop()
    extra_storage_nxdb = mediaserver.nxdb(extra_storage.path)
    extra_storage_nxdb.remove()
    extra_storage_archive.remove_info_files()
    with os.mount_disabled(extra_path):
        mediaserver.start()
        [time_periods] = api.list_recorded_periods([camera.id])
        assert not time_periods

    def fast_scan_finished():
        [time_periods_after] = api.list_recorded_periods([camera.id])
        return time_period_before in time_periods_after

    wait_for_truthy(fast_scan_finished, timeout_sec=60)
    camera_archive = extra_storage_archive.camera_archive(camera.physical_id)
    wait_for_truthy(
        camera_archive.low().has_info,
        timeout_sec=300,
        )
    wait_for_truthy(
        camera_archive.high().has_info,
        timeout_sec=30,  # Already waited long enough for low_archive_info, no need for big timeout
        )
