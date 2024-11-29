# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool


def _test_group_attribute(distrib_url, one_vm_type, ldap_type: str, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v3plus')
    ldap_vm_and_mediaserver_vm_network = exit_stack.enter_context(
        pool.ldap_vm_and_mediaservers_vm_network([one_vm_type], ldap_type))
    [ldap_server_unit, mediaserver_unit] = ldap_vm_and_mediaserver_vm_network
    ldap_server = ldap_server_unit.installation()
    ldap_address = ldap_server_unit.subnet_ip()
    mediaserver = mediaserver_unit.installation()
    api: MediaserverApiV3 = mediaserver.api
    mediaserver.start()
    api.setup_local_system()
    group_name = 'Test Group'
    ldap_server.add_group(group_name)
    another_group_name = 'Another Test Group'
    ldap_server.add_group_with_non_default_object_class(another_group_name)
    search_base_groups = LdapSearchBase(
        base_dn=ldap_server.groups_ou(),
        filter='',
        name='groups',
        )
    api.set_ldap_settings(
        host=ldap_address,
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        search_base=[search_base_groups],
        )
    api.sync_ldap_users()
    ldap_groups = [g for g in api.list_user_groups() if g.is_ldap]
    assert len(ldap_groups) == 2, f"There must be two LDAP groups; received: {ldap_groups}"
    api.set_ldap_settings(
        host=ldap_address,
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        search_base=[search_base_groups],
        group_object_class=ldap_server.non_default_group_object_class(),
        )
    api.sync_ldap_users()
    ldap_groups = [g for g in api.list_user_groups() if g.is_ldap]
    assert len(ldap_groups) == 3, f"There must be three LDAP groups; received: {ldap_groups}"
    [default_group] = [g for g in ldap_groups if g.name == group_name]
    [another_group] = [g for g in ldap_groups if g.name == another_group_name]
    assert not default_group.synced(), f"Group {group_name} must not be synced"
    assert another_group.synced(), f"Group {another_group_name} must be synced"
    api.set_ldap_settings(
        host=ldap_address,
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        search_base=[search_base_groups],
        group_object_class='invalid',
        )
    api.sync_ldap_users()
    ldap_groups = [g for g in api.list_user_groups() if g.is_ldap]
    assert len(ldap_groups) == 3, f"There must be three LDAP groups; received: {ldap_groups}"
    [default_group] = [g for g in ldap_groups if g.name == group_name]
    [another_group] = [g for g in ldap_groups if g.name == another_group_name]
    assert not default_group.synced(), f"Group {group_name} must not be synced"
    assert not another_group.synced(), f"Group {another_group_name} must not be synced"
