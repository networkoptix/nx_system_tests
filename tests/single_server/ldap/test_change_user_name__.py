# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access.ldap.server_installation import GeneratedLDAPUser


def _test_change_user_name(
        distrib_url, one_vm_type, ldap_type: str, exit_stack, expected_new_user: bool):
    # Synchronization with Active Directory and OpenLDAP works differently when the username has changed.
    # - OpenLDAP: both usernames exist - the old one (with a warning icon) and the new one.
    # - Active Directory: only the new username exists.
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
    search_base_users = LdapSearchBase(
        base_dn=ldap_server.users_ou(),
        filter='',
        name='users',
        )
    api.set_ldap_settings(
        host=ldap_address,
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        search_base=[search_base_users],
        )
    api.sync_ldap_users()
    ldap_users = [u for u in api.list_users() if u.is_ldap]
    assert len(ldap_users) == 1, "There should be one LDAP user"
    user_name_edited = f'{generated_ldap_user.uid}_edited'
    ldap_server.change_uid(current_uid=generated_ldap_user.uid, new_uid=user_name_edited)
    api.sync_ldap_users()
    ldap_users = [u for u in api.list_users() if u.is_ldap]
    if expected_new_user:
        assert len(ldap_users) == 2, "There should be two LDAP users"
    else:
        assert len(ldap_users) == 1, "There should be one LDAP user"
    if expected_new_user:
        [old_user] = [u for u in ldap_users if u.name == generated_ldap_user.uid]
        assert not old_user.synced, f"User {old_user.uid} should not be synced"
    [new_user] = [u for u in ldap_users if u.name == user_name_edited]
    assert new_user.synced, f"User {new_user.uid} should be synced"
