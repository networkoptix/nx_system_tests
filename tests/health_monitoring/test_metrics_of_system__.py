# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from ipaddress import ip_network

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import MetricsValues
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.storage_preparation import add_local_storage
from mediaserver_scenarios.storage_preparation import add_offline_smb_storage
from mediaserver_scenarios.storage_preparation import add_smb_storage
from os_access import WindowsAccess
from tests.health_monitoring.common import add_test_cameras
from tests.health_monitoring.common import add_users_and_group
from tests.waiting import wait_for_equal


def _test_system_info(distrib_url, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_api_support(api_version, 'users')
    internal_network = ip_network('10.254.0.0/28')
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    network_and_system = exit_stack.enter_context(pool.system({
        'networks': {
            str(internal_network): {
                'first': None,
                'second': None,
                'third': None,
                'smb': None,
                },
            },
        'machines': [
            {'alias': 'first', 'type': 'ubuntu22'},
            {'alias': 'second', 'type': 'win11'},
            {'alias': 'third', 'type': 'ubuntu22'},
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
    first, first_system_info = prepared_first(network_and_system)
    second, second_system_info = prepared_second(network_and_system)
    third, third_system_info = prepared_third(network_and_system, smb_server, str(smb_ip))

    wait_for_equal(
        get_actual_data,
        args=[[first, second, third]],
        expected=[first_system_info, second_system_info, third_system_info],
        )

    merge_systems(first, second, take_remote_settings=False)
    merged_system_info = MetricsValues.make_system_info(
        servers=2,
        storages=first_system_info['storages'] + second_system_info['storages'],
        cameras=first_system_info['cameras'] + second_system_info['cameras'],
        # Two default admins become one
        users=first_system_info['users'] + second_system_info['users'] - 1,
        )
    wait_for_equal(
        get_actual_data,
        args=[[first, second, third]],
        expected=[merged_system_info, merged_system_info, third_system_info],
        )

    merge_systems(third, first, take_remote_settings=False)
    merged_system_info = MetricsValues.make_system_info(
        servers=3,
        storages=third_system_info['storages'] + merged_system_info['storages'],
        cameras=third_system_info['cameras'] + merged_system_info['cameras'],
        users=third_system_info['users'] + merged_system_info['users'] - 1,
        )
    wait_for_equal(
        get_actual_data,
        args=[[first, second, third]],
        expected=[merged_system_info, merged_system_info, merged_system_info],
        )

    second_id = second.api.get_server_id()
    second.stop()
    wait_for_equal(
        get_actual_data,
        args=[[first, third]],
        expected=[merged_system_info, merged_system_info],
        )
    third.api.remove_server(second_id)

    separated_system_info = MetricsValues.make_system_info(
        servers=2,
        storages=merged_system_info['storages'] - second_system_info['storages'],
        cameras=merged_system_info['cameras'] - second_system_info['cameras'],
        users=merged_system_info['users'] - second_system_info['users'] + 1,
        )
    wait_for_equal(
        get_actual_data,
        args=[[first, third]],
        expected=[separated_system_info, separated_system_info])


def prepared_first(network_and_system):
    [system, _, _] = network_and_system
    first = system['first']
    initial_system_info = first.api.get_metrics('system_info')
    users = add_users_and_group(first)
    cameras = add_test_cameras(first, cameras_count=5)
    expected_system_info = MetricsValues.make_system_info(
        users=initial_system_info['users'] + len(users),
        cameras=initial_system_info['cameras'] + len(cameras),
        )
    return first, expected_system_info


def prepared_second(network_and_system):
    [system, _, _] = network_and_system
    second = system['second']
    initial_system_info = second.api.get_metrics('system_info')
    cameras = add_test_cameras(second, cameras_count=7)
    add_local_storage(second)
    expected_system_info = MetricsValues.make_system_info(
        users=initial_system_info['users'],
        cameras=initial_system_info['cameras'] + len(cameras),
        storages=initial_system_info['storages'] + 1,
        )
    return second, expected_system_info


def prepared_third(network_and_system, smb_server, smb_server_address: str):
    [system, _, _] = network_and_system
    third = system['third']
    initial_system_info = third.api.get_metrics('system_info')
    add_smb_storage(third.api, smb_server.os_access, smb_server_address)
    add_offline_smb_storage(third.api, smb_server.os_access, smb_server_address)
    expected_system_info = MetricsValues.make_system_info(
        storages=initial_system_info['storages'] + 2,
        )
    return third, expected_system_info


def get_actual_data(mediaserver_list):
    actual_data = []
    for server in mediaserver_list:
        actual_data.append(server.api.get_metrics('system_info'))
    return actual_data
