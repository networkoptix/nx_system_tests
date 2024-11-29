# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Groups
from mediaserver_api import LdapContinuousSyncMode
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access.ldap.server_installation import GeneratedLDAPUser


def _test_changing_ldap_synchronization_mode(distrib_url, one_vm_type, ldap_type, exit_stack):
    _logger.info("Prepare the stand")
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version='v3plus')
    [ldap_server_unit, mediaserver_unit] = exit_stack.enter_context(
        pool.ldap_vm_and_mediaservers_vm_network([one_vm_type], ldap_type))
    ldap_server = ldap_server_unit.installation()
    ldap_address = ldap_server_unit.subnet_ip()
    mediaserver = mediaserver_unit.installation()
    api: MediaserverApiV3 = mediaserver.api
    mediaserver.start()
    _logger.info("Create LDAP users and groups")
    ldap_users = [GeneratedLDAPUser('LDAP', 'User1'), GeneratedLDAPUser('LDAP', 'User2')]
    ldap_server.add_users([user.attrs() for user in ldap_users])
    ldap_group_names = ['LDAP_group1', 'LDAP_group2']
    for group_name in ldap_group_names:
        ldap_server.add_group(group_name)
    _logger.info("Configure Mediaserver")
    api.setup_local_system()
    search_base_users = LdapSearchBase(base_dn=ldap_server.users_ou(), filter='', name='users')
    search_base_groups = LdapSearchBase(base_dn=ldap_server.groups_ou(), filter='', name='groups')
    api.set_ldap_settings(
        host=str(ldap_address),
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        search_base=[search_base_users, search_base_groups],
        sync_mode=LdapContinuousSyncMode.GROUPS_ONLY,
        )
    _logger.info("Check users and groups")
    timeout = 10
    started_at = time.monotonic()
    expected_ldap_group_names = set(ldap_group_names)
    while True:
        ldap_custom_group_names = {
            group.name for group in api.list_user_groups()
            if group.is_ldap and group.id != Groups.LDAP_DEFAULT}
        if ldap_custom_group_names == expected_ldap_group_names:
            break
        if time.monotonic() > started_at + timeout:
            raise RuntimeError(
                f"LDAP groups {expected_ldap_group_names} were not synchronized after "
                f"{timeout:.1f} seconds")
        time.sleep(1)
    _logger.info(f"LDAP groups were synchronized after {time.monotonic() - started_at:.1f} seconds")
    ldap_custom_user_names = {user.name for user in api.list_users() if user.is_ldap}
    assert not ldap_custom_user_names, f"Expected no LDAP users, got {ldap_custom_user_names}"
    _logger.info('Change the synchronization mode to continuous')
    api.set_ldap_settings(
        host=str(ldap_address),
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        search_base=[search_base_users, search_base_groups],
        sync_mode=LdapContinuousSyncMode.USERS_AND_GROUPS,
        )
    _logger.info("Check users and groups")
    timeout = 10
    started_at = time.monotonic()
    expected_ldap_user_names = {user.uid for user in ldap_users}
    while True:
        ldap_custom_user_names = {user.name for user in api.list_users() if user.is_ldap}
        if ldap_custom_user_names == expected_ldap_user_names:
            break
        if time.monotonic() > started_at + timeout:
            raise RuntimeError(
                f"LDAP users {expected_ldap_user_names} were not synchronized after "
                f"{timeout:.1f} seconds")
        time.sleep(1)
    _logger.info(f"LDAP users were synchronized after {time.monotonic() - started_at:.1f} seconds")
    ldap_custom_group_names = {
        group.name for group in api.list_user_groups()
        if group.is_ldap and group.id != Groups.LDAP_DEFAULT}
    assert ldap_custom_group_names == expected_ldap_group_names, (
        f"LDAP groups {expected_ldap_group_names} were not synchronized")


_logger = logging.getLogger(__name__)
