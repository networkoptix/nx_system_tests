# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access.ldap.server_installation import GeneratedLDAPUser


def _test_group_members(distrib_url, one_vm_type, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v3plus')
    openldap_vm_and_mediaserver_vm_network = exit_stack.enter_context(
        pool.ldap_vm_and_mediaservers_vm_network([one_vm_type], 'openldap'))
    [ldap_server_unit, mediaserver_unit] = openldap_vm_and_mediaserver_vm_network
    ldap_server = ldap_server_unit.installation()
    ldap_address = ldap_server_unit.subnet_ip()
    mediaserver = mediaserver_unit.installation()
    api: MediaserverApiV3 = mediaserver.api
    mediaserver.start()
    api.setup_local_system()
    initial_generated_ldap_user = GeneratedLDAPUser('Default', 'User')
    another_generated_ldap_user = GeneratedLDAPUser('Another', 'User')
    ldap_server.add_users([initial_generated_ldap_user.attrs()])
    ldap_server.add_users([another_generated_ldap_user.attrs()])
    group_name = 'Test Group'
    ldap_server.add_group(group_name, members=[initial_generated_ldap_user.uid])
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
    [ldap_group] = [g for g in api.list_user_groups() if g.name == group_name]
    [initial_user] = [u for u in api.list_users() if u.name == initial_generated_ldap_user.uid]
    [another_user] = [u for u in api.list_users() if u.name == another_generated_ldap_user.uid]
    assert initial_user.is_group_member(ldap_group.id), f"{initial_user} must be a member of {ldap_group.name}"
    assert not another_user.is_group_member(ldap_group.id), f"{another_user} must not be a member of {ldap_group.name}"
    ldap_server.add_user_to_group(another_generated_ldap_user.uid, group_name)
    ldap_server.remove_user_from_group(initial_generated_ldap_user.uid, group_name)
    api.sync_ldap_users()
    [initial_user] = [u for u in api.list_users() if u.name == initial_generated_ldap_user.uid]
    [another_user] = [u for u in api.list_users() if u.name == another_generated_ldap_user.uid]
    assert not initial_user.is_group_member(ldap_group.id), f"{initial_user} must not be a member of {ldap_group.name}"
    assert another_user.is_group_member(ldap_group.id), f"{another_user} must be a member of {ldap_group.name}"
