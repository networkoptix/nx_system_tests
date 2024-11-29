# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access.ldap.server_installation import GeneratedLDAPUser


def _test_login_attribute(distrib_url, one_vm_type, ldap_type: str, exit_stack):
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
    generated_user_with_email = GeneratedLDAPUser('Test', 'User')
    generated_user_without_email = GeneratedLDAPUser('No', 'Email', has_email=False)
    ldap_server.add_users([
        generated_user_with_email.attrs(),
        generated_user_without_email.attrs(),
        ])
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
        login_attribute='mail',
        )
    api.sync_ldap_users()
    ldap_users = [u for u in api.list_users() if u.is_ldap]
    assert len(ldap_users) == 1, f"There should be only one LDAP user; received {len(ldap_users)}"
    [ldap_user] = ldap_users
    assert ldap_user.name == generated_user_with_email.email, f"User name should be {generated_user_with_email.email}"
    api.set_ldap_settings(
        host=ldap_address,
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        search_base=[search_base_users],
        )
    api.sync_ldap_users()
    ldap_users = [u for u in api.list_users() if u.is_ldap]
    assert len(ldap_users) == 2, f"There should be two LDAP users; received {len(ldap_users)}"
    [ldap_user_with_email] = [u for u in ldap_users if u.name == generated_user_with_email.uid]
    [ldap_user_without_email] = [u for u in ldap_users if u.name == generated_user_without_email.uid]
    assert ldap_user_with_email.synced, f"User {ldap_user_with_email} should be synced"
    assert ldap_user_without_email.synced, f"User {ldap_user_without_email} should be synced"
