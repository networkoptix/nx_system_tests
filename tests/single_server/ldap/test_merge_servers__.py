# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import LdapSearchBase
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_merge_servers(
        distrib_url,
        first_os_name: str,
        first_connected_to_ldap: bool,
        second_os_name: str,
        second_connected_to_ldap: bool,
        master_is_first: bool,
        ldap_type: str,
        exit_stack,
        ):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    api_version = 'v3plus'
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    [ldap_server_unit, mediaserver1_unit, mediaserver2_unit] = exit_stack.enter_context(
        pool.ldap_vm_and_mediaservers_vm_network([first_os_name, second_os_name], ldap_type))
    ldap_server = ldap_server_unit.installation()
    ldap_address = ldap_server_unit.subnet_ip()
    first = mediaserver1_unit.installation()
    first.start()
    first.api.setup_local_system()
    search_base = LdapSearchBase(ldap_server.users_ou(), '', 'users')
    if first_connected_to_ldap:
        first.api.set_ldap_settings(
            ldap_address, ldap_server.admin_dn(), ldap_server.password(), [search_base])
        first.api.sync_ldap_users()
    second = mediaserver2_unit.installation()
    second.start()
    second.api.setup_local_system()
    if second_connected_to_ldap:
        second.api.set_ldap_settings(
            ldap_address, ldap_server.admin_dn(), ldap_server.password(), [search_base])
        second.api.sync_ldap_users()
    before = {
        'first': {
            'ldap_settings': first.api.get_ldap_settings(),
            'groups': first.api.list_user_groups(),
            'users': first.api.list_users(),
            },
        'second': {
            'ldap_settings': second.api.get_ldap_settings(),
            'groups': second.api.list_user_groups(),
            'users': second.api.list_users(),
            }}
    merge_systems(first, second, take_remote_settings=False if master_is_first else True)
    after = {
        'first': {
            'ldap_settings': first.api.get_ldap_settings(),
            'groups': first.api.list_user_groups(),
            'users': first.api.list_users(),
            },
        'second': {
            'ldap_settings': second.api.get_ldap_settings(),
            'groups': second.api.list_user_groups(),
            'users': second.api.list_users(),
            }}
    if first_connected_to_ldap:
        server = 'first'
        assert before[server]['ldap_settings'] == after[server]['ldap_settings'], (
            f"LDAP settings have been changed on the {server!r} server. "
            f"Before: {before[server]['ldap_settings']}, "
            f"after {after[server]['ldap_settings']}"
            )
        assert before[server]['groups'] == after[server]['groups'], (
            f"Groups have been changed on the {server!r} server. "
            f"Before: {before[server]['groups']}, after: {after[server]['groups']}"
            )
        assert before[server]['users'] == after[server]['users'], (
            f"Users have been changed on the {server!r} server. Before: {before[server]['users']}, "
            f"after: {after[server]['users']}"
            )
    if second_connected_to_ldap:
        server = 'second'
        assert before[server]['ldap_settings'] == after[server]['ldap_settings'], (
            f"LDAP settings have been changed on the {server!r} server. "
            f"Before: {before[server]['ldap_settings']}, "
            f"after {after[server]['ldap_settings']}"
            )
        assert before[server]['groups'] == after[server]['groups'], (
            f"Groups have been changed on the {server!r} server. "
            f"Before: {before[server]['groups']}, after: {after[server]['groups']}"
            )
        assert before[server]['users'] == after[server]['users'], (
            f"Users have been changed on the {server!r} server. Before: {before[server]['users']}, "
            f"after: {after[server]['users']}"
            )
