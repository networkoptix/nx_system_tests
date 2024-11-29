# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import time

from cloud_api._cloud import DefaultChannelPartnerRoles
from cloud_api.cloud import assert_channel_partners_supported
from cloud_api.cloud import make_cloud_account_factory
from runner.ft_test import run_ft_test
from tests.base_test import CloudTest


class test_channel_partners(CloudTest):
    """Test Channel Partner requests.

    Selection-Tag: channel_partners_api
    Selection-Tag: cloud_portal_smoke
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        assert_channel_partners_supported(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cp_data = cloud_account_factory.grant_channel_partner_access()
        [root_cp_id, root_cp_admin] = cloud_account_factory.prepare_root_cp_with_admin(cp_data)
        root_admin_cp_api = root_cp_admin.make_channel_partner_api()
        second_account = cloud_account_factory.create_account()
        root_admin_cp_api.update_channel_partner_user(
            root_cp_id,
            second_account.user_email,
            DefaultChannelPartnerRoles['manager'].get_id(),
            title='New User',
            attributes={'TestAttribute': "TestValue"},
            )
        new_name = f'My user {time.perf_counter_ns()}'
        new_partner = root_admin_cp_api.create_channel_partner(
            new_name, root_cp_id, second_account.user_email)
        second_account_cp_api = second_account.make_channel_partner_api()
        partners = second_account_cp_api.list_channel_partners()
        assert len(partners) == 2, f"Expected 2 partners, got {len(partners)}"
        # Roles, role IDs and permissions are empty in POST /v2/channel_partners/ request response.
        # See: https://networkoptix.atlassian.net/browse/CLOUD-14849
        # default_admin_role = DefaultChannelPartnerRoles['admin']
        # assert new_partner.list_roles() == [default_admin_role.get_name()], (
        #     f"Expected {[default_admin_role.get_name()]}, got {new_partner.list_roles()}")
        # assert new_partner.list_role_ids() == [default_admin_role.get_id()], (
        #     f"Expected {[default_admin_role.get_id()]}, got {new_partner.list_role_ids()}")
        assert new_partner.is_active()
        [base, _domain] = root_cp_admin.user_email.split('+defaultadmin@')
        sub_partners = root_admin_cp_api._list_sub_channel_partners(root_cp_id)
        sub_partner_names = [sub_partner.get_name() for sub_partner in sub_partners]
        assert new_name in sub_partner_names, (
            f"Partner with name {new_name} not in {sub_partner_names}")
        partner_base_name = f"{base}'s Default Channel Partner"
        assert partner_base_name in sub_partner_names, (
            f"Partner {partner_base_name} not in {sub_partner_names}")
        new_partner_id = new_partner.get_id()
        actual_name = root_admin_cp_api.get_channel_partner(new_partner_id).get_name()
        assert actual_name == new_name, (
            f"Expected channel partner name {new_name}, got {actual_name}")
        root_admin_cp_api.suspend_channel_partner(new_partner_id)
        assert root_admin_cp_api.get_channel_partner(new_partner_id).is_suspended()
        aggregated_data = root_admin_cp_api.get_aggregated_usage_data(root_cp_id)
        partners_count = aggregated_data.get_channel_partners_count()
        assert partners_count >= len(partners), (
            f"Aggregated partners count {partners_count} < {len(partners)} from general list")
        [expected_partner] = second_account_cp_api.get_channel_structure(new_partner_id)
        assert expected_partner.get_name() == new_name, (
            f"Expected channel partner name {new_name}, got {expected_partner.get_name()}")
        assert expected_partner.is_suspended()
        assert not expected_partner.list_subpartners()
        [root_partner] = root_admin_cp_api.get_self_channel_structure()
        assert len(root_partner.list_subpartners()) >= len(partners), (
            f"Structured partners count {root_partner.list_subpartners()} < {len(partners)} "
            f"from general list")
        root_admin_cp_api.shutdown_channel_partner(new_partner_id)
        assert root_admin_cp_api.get_channel_partner(new_partner_id).is_shutdown()


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_channel_partners()]))
