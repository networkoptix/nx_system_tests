# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access.ldap.server_installation import GeneratedLDAPUser


def _test_sync_1400_users(distrib_url, one_vm_type, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    api_version = 'v3plus'
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    openldap_vm_and_mediaserver_vm_network = exit_stack.enter_context(
        pool.ldap_vm_and_mediaservers_vm_network([one_vm_type], 'openldap'))
    [ldap_server_unit, mediaserver_unit] = openldap_vm_and_mediaserver_vm_network
    ldap_server = ldap_server_unit.installation()
    ldap_address = ldap_server_unit.subnet_ip()
    mediaserver = mediaserver_unit.installation()
    api: MediaserverApiV3 = mediaserver.api
    users_count = 1400
    _generate_ldap_users(count=users_count, ldap_server=ldap_server)
    mediaserver.start()
    api.setup_local_system()
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
    assert len(ldap_users) == users_count, f"Expected {users_count} LDAP users, got {len(ldap_users)}"


def _generate_ldap_users(count, ldap_server):
    user_list = []
    for i in range(count):
        user = GeneratedLDAPUser(
            first_name=f'FirstName{i}',
            second_name=f'SecondName{i}',
            )
        user_list.append(user.attrs())
    ldap_server.add_users(user_list)
