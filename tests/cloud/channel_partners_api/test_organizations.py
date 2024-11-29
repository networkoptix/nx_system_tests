# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from uuid import UUID

from cloud_api import BadRequest
from cloud_api import Forbidden
from cloud_api.channel_partners.organization import AccessLevel
from cloud_api.channel_partners.organization import AccessToDataForbidden
from cloud_api.channel_partners.organization import Roles
from cloud_api.cloud import make_cloud_account_factory
from runner.ft_test import run_ft_test
from tests.base_test import CloudTest
from tests.infra import assert_raises


class test_organizations(CloudTest):
    """Test organization-related API endpoints for Channel Partners.

    Selection-Tag: channel_partners_api
    Selection-Tag: cloud_portal_smoke
    """

    def _run(self, args, exit_stack):
        cloud_account_factory = make_cloud_account_factory(args.cloud_host)
        cp_data = cloud_account_factory.grant_channel_partner_access()
        [_root_cp_id, root_cp_admin] = cloud_account_factory.prepare_root_cp_with_admin(cp_data)
        root_admin_cp_api = root_cp_admin.make_channel_partner_api()
        [regular_cp_id, regular_cp_admin] = cloud_account_factory.prepare_sub_cp_with_admin(cp_data)
        regular_admin_cp_api = regular_cp_admin.make_channel_partner_api()
        [_organization_id, organization_admin] = cloud_account_factory.prepare_cp_organization_with_admin(cp_data)
        organization_admin_cp_api = organization_admin.make_channel_partner_api()
        assert not root_admin_cp_api.list_own_organizations()
        assert not regular_admin_cp_api.list_own_organizations()
        [default_organization] = organization_admin_cp_api.list_own_organizations()
        default_organization_cp_id = default_organization.get_channel_partner_id()
        assert regular_cp_id == default_organization_cp_id, (
            f"{regular_cp_id} != {default_organization_cp_id}")
        default_organization_name_part = 'Default Organization'
        assert default_organization_name_part in default_organization.get_name(), (
            f"{default_organization_name_part} not in {default_organization.get_name()}")
        assert not default_organization.get_attributes()
        [cp_organization] = root_admin_cp_api.list_organizations_for_channel_partner(regular_cp_id)
        default_organization_id = default_organization.get_id()
        cp_organization_id = cp_organization.get_id()
        assert cp_organization_id == default_organization_id, (
            f"{cp_organization_id} != {default_organization_id}")
        with assert_raises(Forbidden):
            organization_admin_cp_api.list_organizations_for_channel_partner(regular_cp_id)
        root_admin_fetched_org = root_admin_cp_api.get_organization(default_organization_id)
        with assert_raises(AccessToDataForbidden):
            root_admin_fetched_org.get_name()
        with assert_raises(AccessToDataForbidden):
            root_admin_fetched_org.get_channel_partner_access_level()
        assert root_admin_fetched_org.get_own_user_role().is_empty()
        viewer_role_id = Roles.VIEWER.get_id()
        with assert_raises(Forbidden):
            root_admin_cp_api.set_organization_user_role(
                organization_id=default_organization_id,
                user_email=root_cp_admin.user_email,
                role_id=viewer_role_id,
                )
        regular_admin_fetched_org = regular_admin_cp_api.get_organization(
            default_organization_id)
        default_org_cp_access_level = default_organization.get_channel_partner_access_level()
        organization_admin_access_level = AccessLevel.organization_admin()
        assert default_org_cp_access_level.is_equal(organization_admin_access_level), (
            f"{default_org_cp_access_level!r} != {organization_admin_access_level!r}")
        regular_admin_org_access_level = regular_admin_fetched_org.get_channel_partner_access_level()
        assert regular_admin_org_access_level.is_equal(organization_admin_access_level), (
            f"{regular_admin_org_access_level!r} != {organization_admin_access_level!r}")
        assert regular_admin_fetched_org.get_own_user_role().is_equal(
            Roles.ORGANIZATION_ADMINISTRATOR)
        organization_admin_fetched_org = organization_admin_cp_api.get_organization(
            default_organization_id)
        org_admin_org_access_level = organization_admin_fetched_org.get_channel_partner_access_level()
        assert org_admin_org_access_level.is_equal(organization_admin_access_level), (
            f"{org_admin_org_access_level!r} != {organization_admin_access_level!r}")
        assert organization_admin_fetched_org.get_own_user_role().is_equal(
            Roles.ORGANIZATION_ADMINISTRATOR)
        regular_admin_cp_api.set_organization_user_role(
            organization_id=default_organization_id,
            user_email=root_cp_admin.user_email,
            role_id=viewer_role_id,
            )
        root_admin_fetched_org = root_admin_cp_api.get_organization(default_organization_id)
        assert root_admin_fetched_org.get_name() == organization_admin_fetched_org.get_name(), (
            f"{root_admin_fetched_org.get_name()} != {organization_admin_fetched_org.get_name()}")
        assert root_admin_fetched_org.get_own_user_role().is_equal(Roles.VIEWER)
        # It is not possible to configure the role per-user for organization users that were
        # inherited from Channel Partner. Only Channel Partner Access level can be configured,
        # and it applies for every user inherited from Channel Partner.
        with assert_raises(BadRequest):
            organization_admin_cp_api.set_organization_user_role(
                organization_id=default_organization_id,
                user_email=regular_cp_admin.user_email,
                role_id=Roles.POWER_USER.get_id(),
                )
        regular_admin_cp_api.set_organization_user_role(
            organization_id=default_organization_id,
            user_email=organization_admin.user_email,
            role_id=Roles.POWER_USER.get_id(),
            )
        organization_admin_fetched_org = organization_admin_cp_api.get_organization(
            default_organization_id)
        assert organization_admin_fetched_org.get_own_user_role().is_equal(Roles.POWER_USER)
        with assert_raises(Forbidden):
            organization_admin_cp_api.set_organization_user_role(
                organization_id=default_organization_id,
                user_email=root_cp_admin.user_email,
                role_id=Roles.ORGANIZATION_ADMINISTRATOR.get_id(),
                )
        regular_admin_cp_api.set_organization_user_role(
            organization_id=default_organization_id,
            user_email=organization_admin.user_email,
            role_id=Roles.ORGANIZATION_ADMINISTRATOR.get_id(),
            )
        organization_admin_cp_api.set_channel_partner_access_level(
            organization_id=default_organization_id,
            access_level_id=AccessLevel.system_health_viewer().get_id(),
            )
        with assert_raises(Forbidden):
            regular_admin_cp_api.set_organization_user_role(
                organization_id=default_organization_id,
                user_email=organization_admin.user_email,
                role_id=Roles.VIEWER.get_id(),
                )
        regular_admin_fetched_org = regular_admin_cp_api.get_organization(
            default_organization_id)
        health_viewer_access_level = AccessLevel.system_health_viewer()
        regular_admin_cp_access_level = regular_admin_fetched_org.get_channel_partner_access_level()
        assert regular_admin_cp_access_level.is_equal(health_viewer_access_level), (
            f"{health_viewer_access_level!r} != {regular_admin_cp_access_level!r}")
        regular_admin_user_role = regular_admin_fetched_org.get_own_user_role()
        assert regular_admin_user_role.is_equal(Roles.SYSTEM_HEALTH_VIEWER), (
            f"{regular_admin_user_role!r} != {Roles.SYSTEM_HEALTH_VIEWER!r}")
        organization_admin_cp_api.set_channel_partner_access_level(
            organization_id=default_organization_id,
            access_level_id=AccessLevel.empty().get_id(),
            )
        regular_admin_fetched_org = regular_admin_cp_api.get_organization(default_organization_id)
        regular_admin_user_role = regular_admin_fetched_org.get_own_user_role()
        assert regular_admin_user_role.is_equal(Roles.EMPTY), (
            f"{regular_admin_user_role!r} != {Roles.EMPTY!r}")
        empty_access_level = AccessLevel.empty()
        regular_admin_cp_access_level = regular_admin_fetched_org.get_channel_partner_access_level()
        assert regular_admin_cp_access_level.is_equal(empty_access_level), (
            f"{regular_admin_cp_access_level!r} != {empty_access_level!r}")
        with assert_raises(BadRequest):
            regular_admin_cp_api.create_organization(
                name='',  # Name is required
                channel_partner_id=regular_cp_id,
                )
        too_long_org_name = '10_symbols' * 16  # The limit is 150 symbols
        with assert_raises(BadRequest):
            regular_admin_cp_api.create_organization(
                name=too_long_org_name,
                channel_partner_id=regular_cp_id,
                )
        new_organization_name = 'New organization'
        invalid_cp_id = UUID('00000000-0000-0000-0000-000000000000')
        with assert_raises(BadRequest):
            regular_admin_cp_api.create_organization(
                name=new_organization_name,
                channel_partner_id=invalid_cp_id,
                )
        new_organization = regular_admin_cp_api.create_organization(
            name=f'  {new_organization_name}  ',
            channel_partner_id=regular_cp_id,
            )
        assert new_organization.get_name() == new_organization_name, (
            f"{new_organization.get_name()} != {new_organization_name}, "
            "possibly leading/trailing spaces weren't removed")
        regular_cp_org_list = regular_admin_cp_api.list_organizations_for_channel_partner(regular_cp_id)
        assert len(regular_cp_org_list) == 2, (
            f"Expected exactly 2 organizations, got {len(regular_cp_org_list)}")
        assert any(org.is_equal(new_organization) for org in regular_cp_org_list), (
            f"{new_organization!r} not found among {regular_cp_org_list!r}")
        with assert_raises(Forbidden):
            organization_admin_cp_api.get_organization(new_organization.get_id())
        new_organization_for_root_admin = root_admin_cp_api.get_organization(
            new_organization.get_id())
        root_admin_role_in_new_org = new_organization_for_root_admin.get_own_user_role()
        assert root_admin_role_in_new_org.is_equal(Roles.EMPTY), (
            f"Root admin has role {root_admin_role_in_new_org!r}. "
            f"Expected to have {Roles.EMPTY}")
        with assert_raises(Forbidden):
            root_admin_cp_api.add_user_to_organization(
                organization_id=new_organization.get_id(),
                user_email=organization_admin.user_email,
                role_id=Roles.POWER_USER.get_id(),
                )
        org_admin_account_in_new_org = regular_admin_cp_api.add_user_to_organization(
            organization_id=new_organization.get_id(),
            user_email=organization_admin.user_email,
            role_id=Roles.POWER_USER.get_id(),
            )
        assert org_admin_account_in_new_org.get_role().is_equal(Roles.POWER_USER), (
            f"{org_admin_account_in_new_org.get_role()!r} != {Roles.POWER_USER!r}")
        test_attributes = {
            'attr_1': 123,
            'attr_2': 456,
            }
        with assert_raises(Forbidden):
            organization_admin_cp_api.update_organization_properties(
                organization_id=new_organization.get_id(),
                properties={'attributes': test_attributes},
                )
        new_organization_for_regular_admin = regular_admin_cp_api.update_organization_properties(
            organization_id=new_organization.get_id(),
            properties={'attributes': test_attributes},
            )
        actual_org_attributes = new_organization_for_regular_admin.get_attributes()
        assert actual_org_attributes == test_attributes, (
            f"{new_organization_for_regular_admin!r} attributes expected to be "
            f"{test_attributes}, got {actual_org_attributes}")
        test_attributes_patch = {
                'attr_1': 'new attr_1 value',
                'attr_3': 333,
                }
        new_organization_for_regular_admin = regular_admin_cp_api.update_organization_properties(
            organization_id=new_organization.get_id(),
            properties={'attributes': test_attributes_patch},
            )
        patched_attributes = {**test_attributes, **test_attributes_patch}
        actual_org_attributes = new_organization_for_regular_admin.get_attributes()
        assert actual_org_attributes == patched_attributes, (
            f"{new_organization_for_regular_admin!r} attributes expected to be "
            f"{patched_attributes}, got {actual_org_attributes}")


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_organizations()]))
