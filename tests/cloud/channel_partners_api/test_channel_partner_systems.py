# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys

from cloud_api import BadRequest
from cloud_api import CannotBindSystemToOrganization
from cloud_api import Forbidden
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.infra import assert_raises


class test_channel_partner_systems(CloudTest, VMSTest):
    """Test Channel Partner Cloud System requests.

    Selection-Tag: channel_partners_api
    """

    def _run(self, args, exit_stack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_host = args.cloud_host
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cp_data = cloud_account_factory.grant_channel_partner_access()
        [org_id, org_admin] = cloud_account_factory.prepare_cp_organization_with_admin(cp_data)
        [_def_cp_id, def_cp_admin] = cloud_account_factory.prepare_sub_cp_with_admin(cp_data)
        def_cp_api = def_cp_admin.make_channel_partner_api()
        org_admin_cp_api = org_admin.make_channel_partner_api()
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        vm_type = 'ubuntu22'
        first_stand = exit_stack.enter_context(pool.one_mediaserver(vm_type))
        services_hosts = org_admin.get_services_hosts()
        first_server = first_stand.mediaserver()
        first_server.os_access.cache_dns_in_etc_hosts([
            cloud_host,
            *services_hosts,
            *public_ip_check_addresses,
            ])
        first_server.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        first_server.set_cloud_host(cloud_host)
        first_server.start()
        first_server.api.setup_local_system(basic_and_digest_auth_required=True)
        first_system_name = first_server.api.get_system_name()
        customization_name = installer_supplier.distrib().customization().customization_name
        try:
            [system_id, auth_key] = org_admin_cp_api.bind_cloud_system_to_organization(
                first_system_name, org_id, customization_name)
        except CannotBindSystemToOrganization:
            raise RuntimeError(
                "Cannot bind system to Channel Partner organization, "
                "probably because of the bug: "
                "https://networkoptix.atlassian.net/browse/CLOUD-15021")
        system_info = org_admin_cp_api.get_system(system_id)
        assert not system_info.system_is_active()
        first_server.api.connect_system_to_cloud(auth_key, system_id, org_admin.user_email)
        org_admin_cp_api.wait_for_active_system(system_id)
        with assert_raises(BadRequest):
            org_admin_cp_api.suspend_channel_partner_for_system(system_id)
        def_cp_api.suspend_channel_partner_for_system(system_id)
        updated_system_info = org_admin_cp_api.get_system(system_id)
        assert updated_system_info.channel_partner_is_suspended()
        updated_system_info = org_admin_cp_api.get_system(system_id)
        assert updated_system_info.channel_partner_is_suspended()
        group_id = def_cp_api.create_group('NewGroup', organization_id=org_id)
        org_admin_cp_api.add_group_for_system(system_id, group_id)
        updated_system_info = org_admin_cp_api.get_system(system_id)
        assert updated_system_info.get_group_id() == group_id, (
            f"{updated_system_info.get_group_id()} != {group_id}")
        organization_systems = org_admin_cp_api.list_systems_in_organization(org_id)
        organization_user_systems = org_admin_cp_api.list_systems_in_organization_for_user(org_id)
        assert len(organization_systems) == len(organization_user_systems), (
            f"{len(organization_systems)} != {len(organization_user_systems)}")
        [org_system] = organization_systems
        [org_user_system] = organization_user_systems
        assert org_system.get_name() == org_user_system.get_name(), (
            f"{org_system.get_name()} != {org_user_system.get_name()}")
        assert org_system.get_organization_id() == org_user_system.get_organization_id(), (
            f"{org_system.get_organization_id()} != {org_user_system.get_organization_id()}")
        assert org_system.system_is_active() == org_user_system.system_is_active(), (
            f"{org_system.system_is_active()} != {org_user_system.system_is_active()}")
        org_admin_cp_api.delete_system(system_id)
        with assert_raises(Forbidden):
            org_admin_cp_api.get_system(system_id)
        assert not org_admin_cp_api.list_systems_in_organization(org_id)
        assert not org_admin_cp_api.list_systems_in_organization_for_user(org_id)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_channel_partner_systems()]))
