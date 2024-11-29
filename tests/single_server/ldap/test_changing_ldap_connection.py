# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
from ipaddress import IPv4Address
from ipaddress import ip_network
from itertools import chain

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Groups
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.provisioned_mediaservers import LdapMachinePool
from os_access.ldap.server_installation import GeneratedLDAPUser
from os_access.ldap.server_installation import LDAPServerInstallation
from runner.ft_test import run_ft_test
from tests.base_test import VMSTest
from vm.networks import setup_flat_network


class test_ubuntu22(VMSTest):
    """Edit LDAP connection settings with/without removing existing LDAP users and groups.

    Selection-Tag: gitlab
    Selection-Tag: 119107
    Selection-Tag: 119108
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/119107
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/119108
    """

    def _run(self, args, exit_stack):
        _test_changing_ldap_connection(args.distrib_url, 'ubuntu22', exit_stack)


def _test_changing_ldap_connection(distrib_url, one_vm_type, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    artifacts_dir = get_run_dir()
    _logger.info("Prepare the stand")
    ldap_vm_pool = LdapMachinePool(artifacts_dir)
    ldap1_vm = exit_stack.enter_context(ldap_vm_pool.ldap_vm('active_directory'))
    ldap2_vm = exit_stack.enter_context(ldap_vm_pool.ldap_vm('openldap'))
    mediaserver_vm_pool = FTMachinePool(installer_supplier, artifacts_dir, 'v3plus')
    mediaserver_stand = exit_stack.enter_context(mediaserver_vm_pool.one_mediaserver(one_vm_type))
    ldap1_vm.ensure_started(artifacts_dir)
    ldap2_vm.ensure_started(artifacts_dir)
    [addresses, _] = setup_flat_network(
        [mediaserver_stand.vm(), ldap1_vm, ldap2_vm], ip_network('10.254.254.0/28'))
    [_, ldap1_address, ldap2_address] = addresses
    api: MediaserverApiV3 = mediaserver_stand.api()
    mediaserver_stand.mediaserver().start()
    api.setup_local_system()
    ldap2_server = exit_stack.enter_context(ldap_vm_pool.ldap_server('openldap', ldap2_vm))
    ldap1_server = exit_stack.enter_context(ldap_vm_pool.ldap_server('active_directory', ldap1_vm))
    _logger.info("Synchronization with a LDAP server")
    _configure_mediaserver_with_ldap(api, ldap1_server, ldap1_address, remove_records=True)
    ldap1_users = [GeneratedLDAPUser('LDAP1', 'User1'), GeneratedLDAPUser('LDAP1', 'User2')]
    ldap1_server.add_users([user.attrs() for user in ldap1_users])
    ldap1_group_names = ['LDAP1_group1', 'LDAP1_group2']
    for group_name in ldap1_group_names:
        ldap1_server.add_group(group_name)
    api.sync_ldap_users()
    _logger.info("Synchronization with another LDAP server")
    ldap2_users = [GeneratedLDAPUser('LDAP2', 'User1'), GeneratedLDAPUser('LDAP2', 'User2')]
    ldap2_server.add_users([user.attrs() for user in ldap2_users])
    ldap2_group_names = ['LDAP2_group1', 'LDAP2_group2']
    for group_name in ldap2_group_names:
        ldap2_server.add_group(group_name)
    _configure_mediaserver_with_ldap(api, ldap2_server, ldap2_address, remove_records=True)
    api.sync_ldap_users()
    _logger.info("Check users and groups with removing existing LDAP users and groups")
    ldap_user_names = {user.name for user in api.list_users() if user.is_ldap}
    expected_ldap_user_names = {user.uid for user in ldap2_users}
    assert ldap_user_names == expected_ldap_user_names, (
        f"Expected LDAP users: {expected_ldap_user_names}, got {ldap_user_names}")
    ldap_custom_group_names = {
        group.name for group in api.list_user_groups() if group.is_ldap and group.id != Groups.LDAP_DEFAULT}
    expected_ldap_group_names = set(ldap2_group_names)
    assert ldap_custom_group_names == expected_ldap_group_names, (
        f"Expected LDAP groups {ldap_custom_group_names}, got {expected_ldap_group_names}")
    _logger.info("Check users and groups without removing existing LDAP users and groups")
    _configure_mediaserver_with_ldap(api, ldap1_server, ldap1_address, remove_records=False)
    api.sync_ldap_users()
    ldap_user_names = {user.name for user in api.list_users() if user.is_ldap}
    expected_ldap_user_names = {user.uid for user in chain(ldap1_users, ldap2_users)}
    assert ldap_user_names == expected_ldap_user_names, (
        f"Expected LDAP users: {expected_ldap_user_names}, got {ldap_user_names}")
    ldap_user_names = {user.name for user in api.list_users() if user.synced}
    expected_ldap_user_names = {user.uid for user in ldap1_users}
    assert ldap_user_names == expected_ldap_user_names, (
        f"Expected synced LDAP users: {expected_ldap_user_names}, got {ldap_user_names}")
    ldap_custom_group_names = {
        group.name for group in api.list_user_groups() if group.is_ldap and group.id != Groups.LDAP_DEFAULT}
    expected_ldap_group_names = {*ldap1_group_names, *ldap2_group_names}
    assert ldap_custom_group_names == expected_ldap_group_names, (
        f"Expected LDAP groups {ldap_custom_group_names}, got {expected_ldap_group_names}")
    ldap_custom_group_names = {
        group.name for group in api.list_user_groups()
        if group.is_ldap and group.synced() and group.id != Groups.LDAP_DEFAULT}
    expected_ldap_group_names = set(ldap1_group_names)
    assert ldap_custom_group_names == expected_ldap_group_names, (
        f"Expected synced LDAP groups {ldap_custom_group_names}, got {expected_ldap_group_names}")


def _configure_mediaserver_with_ldap(
        api: MediaserverApiV3,
        ldap_server: LDAPServerInstallation,
        ldap_address: IPv4Address,
        remove_records: bool,
        ):
    search_base_users = LdapSearchBase(base_dn=ldap_server.users_ou(), filter='', name='users')
    search_base_groups = LdapSearchBase(base_dn=ldap_server.groups_ou(), filter='', name='groups')
    api.set_ldap_settings(
        host=str(ldap_address),
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        search_base=[search_base_users, search_base_groups],
        remove_records=remove_records,
        )


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [
        test_ubuntu22(),
        ]))
