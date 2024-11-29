# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import time
from itertools import chain

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import MediaserverArchive
from mediaserver_api import MediaserverApiV1
from mediaserver_api import TimePeriod
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.software_camera_scenarios import record_from_cameras
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest
from tests.waiting import wait_for_truthy


def add_backup_storages(server, one_vm, storages_dict):
    storages = []
    for (letter, size) in storages_dict.items():
        one_vm.vm_control.add_disk('sata', size)
        path = server.os_access.mount_disk(letter)
        [_, storage] = server.api.set_up_new_storage(path, is_backup=True)
        storages.append(storage)
    return storages


class test_win11_v1(VMSTest):
    """Test disappearing main storage.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/88921
    """

    def _run(self, args, exit_stack):
        _test_disappearing_main_storage(args.distrib_url, ('ubuntu22', 'win11'), 'v1', exit_stack)


def _test_disappearing_main_storage(distrib_url, two_vm_types, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    camera_server = MultiPartJpegCameraServer()
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    vm_and_mediaserver_vm_network = exit_stack.enter_context(pool.vm_and_mediaserver_vm_network(two_vm_types))
    [[iscsi_address, iscsi_server_nic_id, iscsi_machine], mediaserver_unit] = vm_and_mediaserver_vm_network
    server = mediaserver_unit.installation()
    # Set minimal sample duration to make this test faster.
    server.update_conf({'mediaFileDuration': 1})
    server.allow_license_server_access(license_server.url())
    server.start()
    server.api.setup_local_system({'licenseServer': license_server.url()})
    brand = server.api.get_brand()
    key = license_server.generate({'BRAND2': brand, 'QUANTITY2': 100})
    server.api.activate_license(key)
    iscsi_target_iqn = iscsi_machine.os_access.create_iscsi_target(20 * 1000**3, 'test')
    [storage] = add_backup_storages(server, mediaserver_unit.vm(), {'V': 20_000})
    local_backup_archive: MediaserverArchive = server.archive(storage.path)
    api: MediaserverApiV1 = server.api

    [default_storage] = api.list_storages(server.default_archive().storage_root_path())
    api.disable_storage(default_storage.id)
    disk_path = server.os_access.mount_iscsi_disk(iscsi_address, iscsi_target_iqn)
    [_, iscsi_storage] = server.api.set_up_new_storage(disk_path, is_backup=False)
    [camera] = add_cameras(server, camera_server)
    api.enable_secondary_stream(camera.id)
    [time_period] = record_from_cameras(api, [camera], camera_server, 10)
    main_archive = server.archive(iscsi_storage.path)
    main_camera_archive = main_archive.camera_archive(camera.physical_id)
    wait_for_truthy(
        _whole_video_is_saved_on_storage,
        args=[time_period, main_camera_archive])
    time.sleep(10)
    _whole_video_is_saved_on_storage(time_period, main_camera_archive)
    # Limit backup bandwidth to reduce video size to make the test run faster.
    api.limit_backup_bandwidth(bytes_per_sec=250 * 1000)
    api.enable_backup_for_cameras([camera.id])

    iscsi_storage = api.get_storage(iscsi_storage.id)
    assert iscsi_storage.is_online
    iscsi_machine.vm_control.disconnect_cable(iscsi_server_nic_id)
    wait_for_truthy(
        lambda: not api.get_storage(iscsi_storage.id).is_online,
        description="main storage is offline",
        timeout_sec=150,
        )
    iscsi_machine.vm_control.connect_cable(iscsi_server_nic_id)
    wait_for_truthy(
        lambda: api.get_storage(iscsi_storage.id).is_online,
        description="main storage is online",
        timeout_sec=150,
        )
    assert _whole_video_is_saved_on_storage(time_period, main_camera_archive)
    api.set_unlimited_backup_bandwidth()
    api.wait_for_backup_state_changed(camera.id, timeout_sec=5)
    api.wait_for_backup_finish()
    local_backup_camera_archive = local_backup_archive.camera_archive(camera.physical_id)
    split_low_backup_period = local_backup_camera_archive.low().list_periods()
    split_high_backup_period = local_backup_camera_archive.high().list_periods()
    [low_backup_period] = TimePeriod.consolidate(split_low_backup_period, tolerance_sec=1)
    [high_backup_period] = TimePeriod.consolidate(split_high_backup_period, tolerance_sec=1)
    assert low_backup_period.complete
    assert time_period.is_among([low_backup_period])
    assert high_backup_period.complete
    assert time_period.is_among([high_backup_period])


def _whole_video_is_saved_on_storage(expected_period, camera_archive):
    low_quality_periods = camera_archive.low().list_periods()
    high_quality_periods = camera_archive.high().list_periods()
    if not all(p.complete for p in chain(low_quality_periods, high_quality_periods)):
        return False
    whole_low_quality_is_saved = expected_period.is_among(low_quality_periods)
    whole_high_quality_is_saved = expected_period.is_among(high_quality_periods)
    return whole_low_quality_is_saved and whole_high_quality_is_saved


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_win11_v1()]))
