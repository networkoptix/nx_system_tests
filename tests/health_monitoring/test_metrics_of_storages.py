# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import time
from datetime import timedelta
from ipaddress import ip_network

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import MetricsValues
from mediaserver_api import raw_differ
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.storage_preparation import add_local_storage
from mediaserver_scenarios.storage_preparation import add_network_storage
from mediaserver_scenarios.storage_preparation import add_offline_smb_storage
from mediaserver_scenarios.storage_preparation import add_smb_storage
from os_access import WindowsAccess
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest


class test_v0(VMSTest):
    """Test storages.

    Selection-Tag: gitlab
    See: https://networkoptix.atlassian.net/browse/FT-508
    See: https://networkoptix.atlassian.net/browse/FT-514
    See: https://networkoptix.atlassian.net/browse/FT-515
    See: https://networkoptix.atlassian.net/browse/FT-676
    See: https://networkoptix.atlassian.net/browse/FT-762
    See: https://networkoptix.atlassian.net/browse/FT-763
    See: https://networkoptix.atlassian.net/browse/FT-764
    See: https://networkoptix.atlassian.net/browse/FT-766
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58220
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58226
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58227
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58260
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58259
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58261
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58228
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65714
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65720
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58281
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58283
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58297
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58286
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/58287
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57420
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57421
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57422
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57423
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57424
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/57425
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65711
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65713
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65715
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65716
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65717
    """

    def _run(self, args, exit_stack):
        _test_storages(args.distrib_url, 'v0', exit_stack)


def _test_storages(distrib_url, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    internal_network = ip_network('10.254.0.0/28')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    network_and_system = exit_stack.enter_context(pool.system({
        'networks': {
            str(internal_network): {
                'first': None,
                'second': None,
                'smb': None,
                },
            },
        'machines': [
            {'alias': 'first', 'type': 'ubuntu22'},
            {'alias': 'second', 'type': 'win11'},
            {'alias': 'smb', 'type': 'win11'},
            ],
        'mergers': [],
        }))
    [system, _, addresses] = network_and_system
    for one_system in system.values():
        if isinstance(one_system.os_access, WindowsAccess):
            one_system.os_access.disable_netprofm_service()
    smb_server = system['smb']
    [smb_ip, _smb_nic] = addresses['smb'][internal_network]
    # Stop mediaserver service because it is not needed on this machine
    # TODO: do not install mediaserver in first place
    smb_server.stop()
    first, first_storages = prepared_first(network_and_system, smb_server, str(smb_ip))
    second, second_storages = prepared_second(network_and_system, smb_server, str(smb_ip))
    first.api.wait_for_metric('system_info', 'storages', expected=len(first_storages), timeout_sec=5)
    second.api.wait_for_metric('system_info', 'storages', expected=len(second_storages), timeout_sec=5)
    merge_systems(first, second, take_remote_settings=False)
    merged_storages = {**first_storages, **second_storages}
    first.api.wait_for_metric('system_info', 'storages', expected=len(merged_storages), timeout_sec=5)
    second.api.wait_for_metric('system_info', 'storages', expected=len(merged_storages), timeout_sec=5)
    actual_data = get_actual_storages(first, second)
    expected_data = [merged_storages, merged_storages]
    data_diff = raw_differ.diff(actual_data, expected_data)  # After merge
    assert not data_diff
    second.stop()
    stopped_storages = {
        storage_id: MetricsValues.make_storages(
            type=storage['type'],
            server_id=storage['server_id'],
            location=storage['location'],
            status='Server Offline',
            )
        for storage_id, storage in second_storages.items()
        }
    actual_data = get_actual_storages(first)
    expected_data = [{**first_storages, **stopped_storages}]
    assert not raw_differ.diff(actual_data, expected_data)  # After second server stopped
    second.start()
    for api in first.api, second.api:
        any_smb_storage, *_ = api.list_storages(ignore_offline=True, storage_type='smb')
        api.remove_resource(any_smb_storage.id)
    first.api.wait_for_metric(
        'system_info', 'storages', expected=len(first_storages) + len(second_storages) - 2)


def prepared_first(network_and_system, smb_server, smb_server_address: str):
    [system, _, _] = network_and_system
    first = system['first']
    [default_storage] = first.api.list_storages()
    local_path = add_local_storage(first, storage_size_bytes=15 * 1024**3)
    local_disabled_path = add_local_storage(first, storage_size_bytes=300 * 1024**3)
    smb_share = add_smb_storage(
        first.api,
        smb_server.os_access,
        smb_server_address,
        storage_size_bytes=300 * 1024**3,
        )
    mount_point = add_network_storage(
        first.api,
        first.os_access,
        smb_server.os_access,
        smb_server_address,
        )
    storages = first.api.list_storages()
    [local_storage] = [s for s in storages if s.path.startswith(str(local_path))]
    [disabled_storage] = [s for s in storages if s.path.startswith(str(local_disabled_path))]
    first.api.disable_storage(disabled_storage.id)
    [smb_storage] = [s for s in storages if s.path == smb_share.url]
    [network_storage] = [s for s in storages if s.path.startswith(mount_point)]

    server_time = first.api.get_datetime()
    bitrate_bps = 68 * 10**6  # 4K 60 FPS
    default_archive_size_bytes = default_storage.free_space - 11 * 1024**3
    default_camera_archive = first.default_archive().camera_archive('92-61-00-00-00-01')
    default_camera_archive.high().add_fake_record(
        start_time=server_time - timedelta(days=1),
        duration_sec=default_archive_size_bytes * 8 / bitrate_bps,
        bitrate_bps=bitrate_bps,
        )
    smb_archive_size_bytes = 5 * 1024**3
    smb_archive = first.archive_on_remote(smb_server.os_access, smb_share.local_path)
    smb_camera_archive = smb_archive.camera_archive('92-61-00-00-00-02')
    smb_camera_archive.high().add_fake_record(
        start_time=server_time - timedelta(days=1),
        duration_sec=smb_archive_size_bytes * 8 / bitrate_bps,
        bitrate_bps=bitrate_bps,
        )
    first.api.restart()
    first.api.rebuild_main_archive()
    server_id = first.api.get_server_id()

    default_storage_params = {
        'status': 'Online',
        'server_id': server_id,
        'location': default_storage.path,
        }
    local_storage_params = {
        'status': 'Online',
        'server_id': server_id,
        'location': local_storage.path,
        }
    expected_storages = {
        default_storage.id: MetricsValues.make_storages(**default_storage_params),
        local_storage.id: MetricsValues.make_storages(**local_storage_params),
        disabled_storage.id: MetricsValues.make_storages(
            status='Disabled',
            server_id=server_id,
            location=disabled_storage.path,
            ),
        smb_storage.id: MetricsValues.make_storages(
            status='Online',
            type='smb',
            server_id=server_id,
            location=smb_storage.path.replace('smb://', ''),
            ),
        network_storage.id: MetricsValues.make_storages(
            status='Online',
            type='network',
            server_id=server_id,
            location=network_storage.path,
            ),
        }

    return first, expected_storages


def prepared_second(network_and_system, smb_server, smb_server_host: str):
    [system, _, _] = network_and_system
    second = system['second']
    [default_storage] = second.api.list_storages()
    second.api.reserve_storage_space(default_storage.id, 25 * 1024**3)
    local_backup_path = add_local_storage(second, storage_size_bytes=30 * 1024**3)
    local_main_path = add_local_storage(second, storage_size_bytes=30 * 1024**3)
    smb_share = add_offline_smb_storage(second.api, smb_server.os_access, smb_server_host)
    storages = second.api.list_storages(ignore_offline=True)
    [local_backup_storage] = [s for s in storages if s.path.startswith(str(local_backup_path))]
    second.api.allocate_storage_for_analytics(local_backup_storage.id)
    [local_main_storage] = [s for s in storages if s.path.startswith(str(local_main_path))]
    [smb_storage] = [s for s in storages if s.path == smb_share.url]
    second.api.allocate_storage_for_backup(local_backup_storage.id)
    local_archive_size_bytes = 3 * 1024**3
    server_time = second.api.get_datetime()
    local_backup_storage_obj = second.archive(local_backup_storage.path)
    local_backup_camera_archive = local_backup_storage_obj.camera_archive('92-61-00-00-00-03')
    bitrate_bps = 68 * 10**6  # 4K 60 FPS
    local_backup_camera_archive.high().add_fake_record(
        start_time=server_time - timedelta(days=1),
        duration_sec=local_archive_size_bytes * 8 / bitrate_bps,
        bitrate_bps=bitrate_bps,
        )
    second.api.restart()
    second.api.rebuild_main_archive()
    server_id = second.api.get_server_id()

    expected_storages = {
        default_storage.id: MetricsValues.make_storages(
            status='Online',
            server_id=server_id,
            location=default_storage.path,
            ),
        local_main_storage.id: MetricsValues.make_storages(
            status='Online',
            server_id=server_id,
            location=local_main_storage.path,
            ),
        local_backup_storage.id: MetricsValues.make_storages(
            status='Online',
            server_id=server_id,
            location=local_backup_storage.path,
            ),
        smb_storage.id: MetricsValues.make_storages(
            type='smb',
            server_id=server_id,
            location=smb_storage.path.replace('smb://', ''),
            ),
        }

    return second, expected_storages


def get_actual_storages(*mediaservers):
    skipping_metrics = [
        'total_bytes',
        'used_bytes',
        'used_ratio',
        'read_bytes_per_sec',
        'write_bytes_per_sec',
        'transactions_per_sec',
        ]
    actual_storages = []
    for server in mediaservers:
        # Workaround for VMS-16364
        started_at = time.monotonic()
        while True:
            metrics = server.api.get_metrics('storages')
            if any(s.get('status', '') == 'Online' for s in metrics.values()):
                break
            if time.monotonic() - started_at > 90:
                raise RuntimeError("Neither of storages went Online for long")
            time.sleep(1)
        for storage_metrics in metrics.values():
            for metric_name in skipping_metrics:
                storage_metrics.pop(metric_name, None)
        actual_storages.append(metrics)
    return actual_storages


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_v0()]))
