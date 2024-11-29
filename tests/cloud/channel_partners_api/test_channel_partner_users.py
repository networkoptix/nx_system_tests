# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys

from cloud_api._cloud import DefaultChannelPartnerRoles
from cloud_api.cloud import assert_channel_partners_supported
from cloud_api.cloud import make_cloud_account_factory
from runner.ft_test import run_ft_test
from tests.base_test import CloudTest


class test_channel_partner_users(CloudTest):
    """Test Channel Partner Users requests.

    Selection-Tag: channel_partners_api
    Selection-Tag: cloud_portal_gitlab
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
        third_account = cloud_account_factory.create_account()
        roles = root_admin_cp_api.list_available_roles()
        assert len(roles) == 3
        default_administrator_role = DefaultChannelPartnerRoles['admin']
        default_manager_role = DefaultChannelPartnerRoles['manager']
        default_reports_viewer_role = DefaultChannelPartnerRoles['reports_viewer']
        for role in roles:
            if role.get_name() == default_administrator_role.get_name():
                assert role.get_id() == default_administrator_role.get_id(), (
                    f"{role.get_id()} != {default_administrator_role.get_id()}")
                assert role.list_permissions() == default_administrator_role.list_permissions(), (
                    f"{role.list_permissions()} != {default_administrator_role.list_permissions()}")
                roles.remove(role)
            elif role.get_name() == default_manager_role.get_name():
                assert role.get_id() == default_manager_role.get_id(), (
                    f"{role.list_permissions()} != {default_manager_role.get_id()}")
                assert role.list_permissions() == default_manager_role.list_permissions(), (
                    f"{role.list_permissions()} != {default_manager_role.list_permissions()}")
                roles.remove(role)
            elif role.get_name() == default_reports_viewer_role.get_name():
                assert role.get_id() == default_reports_viewer_role.get_id(), (
                    f"{role.get_id()} != {default_reports_viewer_role.get_id()}")
                assert role.list_permissions() == default_reports_viewer_role.list_permissions(), (
                    f"{role.list_permissions()} != {default_reports_viewer_role.list_permissions()}")
                roles.remove(role)
            else:
                raise RuntimeError(f'Unexpected role: {role.get_raw_data()}')
        assert len(root_admin_cp_api.list_channel_partner_users(root_cp_id)) > 1
        expected_title = 'Test Manager'
        expected_attributes = {'TestAttribute': "TestValue"}
        root_admin_cp_api.update_channel_partner_user(
            root_cp_id,
            second_account.user_email,
            default_manager_role.get_id(),
            title=expected_title,
            attributes=expected_attributes,
            )
        subpartner = root_admin_cp_api.get_subpartner_by_email(
            root_cp_id, second_account.user_email)
        assert subpartner.list_roles() == [default_manager_role.get_name()], (
            f"{subpartner.list_roles()} != {[default_reports_viewer_role.get_name()]}")
        assert subpartner.get_title() == expected_title, (
            f"{subpartner.get_title()} != {expected_title}")
        assert subpartner.list_attributes() == expected_attributes, (
            f"{subpartner.list_attributes()} != {expected_attributes}")
        assert subpartner.list_role_ids() == [default_manager_role.get_id()], (
            f"{subpartner.list_role_ids()} != {[default_manager_role.get_id()]}")
        new_title = 'Test Reports Viewer'
        root_admin_cp_api.update_channel_partner_user(
            root_cp_id,
            second_account.user_email,
            default_reports_viewer_role.get_id(),
            title=new_title,
            )
        subpartner = root_admin_cp_api.get_subpartner_by_email(root_cp_id, second_account.user_email)

        assert subpartner.list_roles() == [default_reports_viewer_role.get_name()], (
            f"{subpartner.list_roles()} != {[default_reports_viewer_role.get_name()]}")
        assert subpartner.get_title() == new_title, (
            f"{subpartner.get_title()} != {new_title}")
        assert subpartner.list_attributes() == expected_attributes, (
            f"{subpartner.list_attributes()} != {expected_attributes}")
        assert subpartner.list_role_ids() == [default_reports_viewer_role.get_id()], (
            f"{subpartner.list_role_ids()} != {[default_reports_viewer_role.get_id()]}")
        users_asc = root_admin_cp_api.get_paginated_subpartners_list(root_cp_id, 'created')
        users_desc = root_admin_cp_api.get_paginated_subpartners_list(root_cp_id, '-created')
        assert users_asc[0].get_email() == users_desc[-1].get_email(), (
            f"{users_asc[0].get_email()} != {users_desc[-1].get_email()}")
        assert users_asc[-1].get_email() == users_desc[0].get_email(), (
            f"{users_asc[-1].get_email()} != {users_desc[0].get_email()}")
        self_info = root_admin_cp_api.get_current_user_record(root_cp_id)
        assert self_info.get_email() == root_cp_admin.user_email, (
            f"{self_info.get_email()} != {root_cp_admin.user_email}")
        assert self_info.list_roles() == [default_administrator_role.get_name()], (
            f"{self_info.list_roles()} != {[default_administrator_role.get_name()]}")
        assert self_info.list_role_ids() == [default_administrator_role.get_id()], (
            f"{self_info.list_role_ids()} != {[default_administrator_role.get_id()]}")
        root_admin_cp_api.update_channel_partner_user(
            root_cp_id, third_account.user_email, default_manager_role.get_id())
        additional_account_emails = [second_account.user_email, third_account.user_email]
        root_admin_cp_api.bulk_delete_users(root_cp_id, additional_account_emails)
        subpartner_emails = root_admin_cp_api.list_subpartners_emails(root_cp_id)
        assert all(email not in subpartner_emails for email in additional_account_emails)
        root_admin_cp_api.update_channel_partner_user(
            root_cp_id,
            second_account.user_email,
            default_reports_viewer_role.get_id(),
            title=new_title,
            )
        subpartner = root_admin_cp_api.get_subpartner_by_email(
            root_cp_id, second_account.user_email)
        assert subpartner.list_roles() == [default_reports_viewer_role.get_name()], (
            f"{subpartner.list_roles()} != {[default_reports_viewer_role.get_name()]}")
        root_admin_cp_api.delete_subpartner(root_cp_id, second_account.user_email)
        subpartners_emails = root_admin_cp_api.list_subpartners_emails(root_cp_id)
        assert second_account.user_email not in subpartners_emails, (
            f"{second_account.user_email} is seen among {subpartners_emails}")


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_channel_partner_users()]))
