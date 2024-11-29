# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access.ldap.server_installation import GeneratedLDAPUser


def _test_invalid_login_attribute(distrib_url, one_vm_type, ldap_type: str, exit_stack):
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
    generated_user = GeneratedLDAPUser('Test', 'User')
    ldap_server.add_users([generated_user.attrs()])
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
    assert len(ldap_users) == 1, f"There should be one LDAP user; received {len(ldap_users)}"
    api.set_ldap_settings(
        host=ldap_address,
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        search_base=[search_base_users],
        login_attribute='invalid',
        )
    api.sync_ldap_users()
    ldap_users = [u for u in api.list_users() if u.is_ldap]
    assert len(ldap_users) == 1, f"There should be one LDAP user; received {len(ldap_users)}"
    [ldap_user] = ldap_users
    assert not ldap_user.synced, f"User {ldap_user} should not  be synced"
