# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access.ldap.server_installation import GeneratedLDAPUser


def _test_rename_group(distrib_url, one_vm_type, ldap_type: str, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    api_version = 'v3plus'
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    ldap_vm_and_mediaserver_vm_network = exit_stack.enter_context(
        pool.ldap_vm_and_mediaservers_vm_network([one_vm_type], ldap_type))
    [ldap_server_unit, mediaserver_unit] = ldap_vm_and_mediaserver_vm_network
    ldap_server = ldap_server_unit.installation()
    ldap_address = ldap_server_unit.subnet_ip()
    mediaserver = mediaserver_unit.installation()
    api: MediaserverApiV3 = mediaserver.api
    mediaserver.start()
    api.setup_local_system()
    generated_ldap_user = GeneratedLDAPUser('Test', 'User')
    ldap_server.add_users([generated_ldap_user.attrs()])
    group_name = 'Test Group'
    ldap_server.add_group(group_name)
    search_base_users = LdapSearchBase(
        base_dn=ldap_server.users_ou(),
        filter='',
        name='users',
        )
    search_base_groups = LdapSearchBase(
        base_dn=ldap_server.groups_ou(),
        filter='',
        name='groups',
        )
    api.set_ldap_settings(
        host=ldap_address,
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        search_base=[search_base_users, search_base_groups],
        )
    api.sync_ldap_users()
    ldap_groups = [g for g in api.list_user_groups() if g.is_ldap]
    assert len(ldap_groups) == 2, f"There must be two LDAP groups; received: {ldap_groups}"
    group_name_edited = f'{group_name} Edited'
    ldap_server.rename_group(current_name=group_name, new_name=group_name_edited)
    api.sync_ldap_users()
    ldap_groups = [g for g in api.list_user_groups() if g.is_ldap]
    assert len(ldap_groups) == 3, f"There must be three LDAP groups; received: {ldap_groups}"
    [group_original] = [g for g in ldap_groups if g.name == group_name]
    [group_edited] = [g for g in ldap_groups if g.name == group_name_edited]
    assert not group_original.synced(), f"Group {group_name} must not be synced"
    assert group_edited.synced(), f"Group {group_name_edited} must be synced"
