# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import time
from ipaddress import IPv4Network
from typing import Collection
from typing import Mapping

from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.infra import assert_raises
from vm.networks import setup_flat_network


class test_system(VMSTest, CloudTest):
    """Test system-related requests.

    Selection-Tag: cloud_db
    """

    def _run(self, args, exit_stack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_host = args.cloud_host
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        vm_type = 'ubuntu22'
        first_stand = exit_stack.enter_context(pool.one_mediaserver(vm_type))
        second_stand = exit_stack.enter_context(pool.one_mediaserver(vm_type))
        cloud_account = cloud_account_factory.create_account()
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_account.set_user_customization(customization_name)
        services_hosts = cloud_account.get_services_hosts()
        setup_flat_network(
            [first_stand.vm(), second_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        first_server = first_stand.mediaserver()
        first_server.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        first_server.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        first_server.set_cloud_host(cloud_host)
        first_server.start()
        first_auth_key = first_server.api.setup_cloud_system(cloud_account)
        first_system_id = first_server.api.get_cloud_system_id()
        second_server = second_stand.mediaserver()
        second_server.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        second_server.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        second_server.set_cloud_host(cloud_host)
        second_server.start()
        second_server.api.setup_cloud_system(cloud_account)
        second_system_id = second_server.api.get_cloud_system_id()
        assert len(cloud_account.get_systems()) == 2
        assert cloud_account.get_system(first_system_id)['status'] == 'activated'
        first_system_name = f'First_test_system_{int(time.perf_counter_ns())}'
        cloud_account.rename_system(first_system_id, first_system_name)
        assert cloud_account.get_system(first_system_id)['name'] == first_system_name
        expected_settings = [
            'onlineStatusExpirationPeriodMs',
            'recommendedUserListPollPeriodMs',
            'recommendedSystemAttributesPollPeriodMs',
            ]
        actual_sync_settings = cloud_account.get_data_sync_settings(first_system_id)
        assert all([actual_sync_settings.get(setting) for setting in expected_settings])
        # TODO: Uncomment or remove when the solution is done on the existing bug.
        # Now, there is an empty list of events is returned whether events have happened or not.
        # first_server.stop()
        # time.sleep(2)
        # first_server.start()
        # assert cloud_account.list_health_history(first_system_id) != []
        # See: https://networkoptix.atlassian.net/browse/CB-2506
        assert cloud_account.auth_key_is_valid(first_system_id, first_auth_key)
        wrong_auth_key = 'SOmErAnD0MKeyqa123Ba'
        assert not cloud_account.auth_key_is_valid(first_system_id, wrong_auth_key)
        cloud_account.merge_systems(first_system_id, second_system_id)
        assert len(cloud_account.get_systems()) == 1
        capabilities = cloud_account.list_attributes(first_system_id)
        expected_cloud_account_id = str(cloud_account.get_user_info().get_id())
        actual_cloud_account_id = _get_attribute_by_name(capabilities, 'ownerAccountId')
        assert expected_cloud_account_id == actual_cloud_account_id, (
            f'{expected_cloud_account_id} != {actual_cloud_account_id}')
        capability_name = 'stub_plugin_names_with_comma_instead_of_colon'
        assert capability_name in _get_attribute_by_name(capabilities, 'capabilities')
        new_attribute_name = 'my_attribute'
        new_attribute_value = 'my_value'
        cloud_account.add_attribute(first_system_id, new_attribute_name, new_attribute_value)
        new_capabilities = cloud_account.list_attributes(first_system_id)
        new_attribute_value = _get_attribute_by_name(new_capabilities, new_attribute_name)
        assert new_attribute_value == new_attribute_value
        updated_value = 'updated_value'
        cloud_account.update_attribute(first_system_id, new_attribute_name, updated_value)
        updated_capabilities = cloud_account.list_attributes(first_system_id)
        updated_attribute_value = _get_attribute_by_name(
            updated_capabilities,
            new_attribute_name,
            )
        assert updated_attribute_value == updated_value
        extra_attribute_name = 'extra_name'
        extra_attribute_value = 'extra_value'
        second_updated_value = 'updated_as_group'
        updated_attributes = [
            {'name': extra_attribute_name, 'value': extra_attribute_value},
            {'name': new_attribute_name, 'value': second_updated_value},
            ]
        cloud_account.update_attributes(first_system_id, updated_attributes)
        updated_capabilities = cloud_account.list_attributes(first_system_id)
        updated_attribute_value = _get_attribute_by_name(
            updated_capabilities,
            new_attribute_name,
            )
        added_attribute_value = _get_attribute_by_name(
            updated_capabilities,
            extra_attribute_name,
            )
        assert updated_attribute_value == second_updated_value
        assert added_attribute_value == extra_attribute_value
        cloud_account.remove_attribute(first_system_id, new_attribute_name)
        attributes_after_removing = cloud_account.list_attributes(first_system_id)
        with assert_raises(KeyError):
            _get_attribute_by_name(attributes_after_removing, new_attribute_name)


def _get_attribute_by_name(attributes: Collection[Mapping[str, str]], expected_name: str) -> str:
    for element in attributes:
        if element['name'] == expected_name:
            return element['value']
    raise KeyError(
        f"Could not find attribute block {expected_name} in attributes list. "
        f"Received attributes: {attributes}")


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_system()]))
