# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access.ldap.server_installation import GeneratedLDAPUser


def _test_remove_ldap_user(distrib_url, one_vm_type, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    api_version = 'v3plus'
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    openldap_vm_and_mediaserver_vm_network = exit_stack.enter_context(
        pool.ldap_vm_and_mediaservers_vm_network([one_vm_type], 'openldap'))
    [ldap_server_unit, mediaserver_unit] = openldap_vm_and_mediaserver_vm_network
    ldap_server = ldap_server_unit.installation()
    ldap_address = ldap_server_unit.subnet_ip()
    mediaserver = mediaserver_unit.installation()
    mediaserver.start()
    api: MediaserverApiV3 = mediaserver.api
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
    [ldap_user] = [u for u in api.list_users() if u.is_ldap]
    api.remove_user(ldap_user.id)
    all_users = api.list_users()
    assert len(all_users) == 1, f"A single user must be left after LDAP user removal while {all_users} received"
    [user] = all_users
    assert not user.is_ldap, "The only user must not be an LDAP user"
    assert user.is_admin, "The only user must be admin"
    assert user.name != ldap_user.name, f"The only user must not be {ldap_user.name}"
    assert user.name != generated_ldap_user.uid, f"The only user must not be {generated_ldap_user.uid}"
