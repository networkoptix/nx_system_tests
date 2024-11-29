# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access.ldap.server_installation import GeneratedLDAPUser


def _test_without_search_base(distrib_url, one_vm_type, exit_stack):
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
    mediaserver.start()
    api.setup_local_system()
    generated_ldap_user = GeneratedLDAPUser('Test', 'User')
    ldap_server.add_users([generated_ldap_user.attrs()])
    api.set_ldap_settings(
        host=ldap_address,
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        )
    api.sync_ldap_users()
    all_users = api.list_users()
    assert len(all_users) == 1, "There must be only one user"
    [user] = all_users
    assert not user.is_ldap, "User must not be LDAP user"
    assert user.is_admin, "User must be admin"
    user_groups = api.list_user_groups()
    [ldap_group] = [g for g in user_groups if g.is_ldap]
    group_name = 'LDAP Default'
    assert ldap_group.name == group_name, f"LDAP group name must be {group_name}"
