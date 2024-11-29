# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access.ldap.server_installation import GeneratedLDAPUser


def _test_sync_users(distrib_url, one_vm_type, ldap_type: str, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    api_version = 'v3plus'
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    _logger.info("Prepare the stand")
    [ldap_server_unit, mediaserver_unit] = exit_stack.enter_context(
        pool.ldap_vm_and_mediaservers_vm_network([one_vm_type], ldap_type))
    ldap_server = ldap_server_unit.installation()
    ldap_address = ldap_server_unit.subnet_ip()
    mediaserver = mediaserver_unit.installation()
    api: MediaserverApiV3 = mediaserver.api
    mediaserver.start()
    api.setup_local_system()
    search_base_users = LdapSearchBase(base_dn=ldap_server.users_ou(), filter='', name='users')
    search_base_groups = LdapSearchBase(base_dn=ldap_server.groups_ou(), filter='', name='groups')
    api.set_ldap_settings(
        host=ldap_address,
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        search_base=[search_base_users, search_base_groups],
        )
    api.sync_ldap_users()
    _logger.info(
        "Verify that LDAP users and groups are imported into Mediaserver after synchronization")
    generated_ldap_user = GeneratedLDAPUser('Test', 'User')
    ldap_server.add_users([generated_ldap_user.attrs()])
    test_group_name = 'Test Group'
    ldap_server.add_group(test_group_name)
    ldap_users = [u for u in api.list_users() if u.is_ldap]
    assert not ldap_users, f"Expected no LDAP users before synchronization, but got {ldap_users}"
    ldap_groups = [g.name for g in api.list_user_groups() if g.is_ldap]
    assert len(ldap_groups) == 1, (
        f"Expected only one ('LDAP Default') group before synchronization, but got {ldap_groups}")
    api.sync_ldap_users()
    [ldap_user] = [u for u in api.list_users() if u.is_ldap]
    assert ldap_user.is_ldap
    # LDAP users should be enabled immediately after synchronization by design.
    # Documentation is still in development, so it doesn't explicitly mention
    # this, but this behavior is required for features such as LDAP user
    # authentication to work without first adding them to the server.
    # See: https://networkoptix.atlassian.net/wiki/spaces/FS/pages/877330465
    assert ldap_user.is_enabled
    ldap_groups = {g.name for g in api.list_user_groups() if g.is_ldap}
    expected_ldap_groups = {'LDAP Default', test_group_name}
    assert ldap_groups == expected_ldap_groups, (
        f"Expected groups: {expected_ldap_groups}, but got {ldap_groups}")
    _logger.info(
        "Verify that changes in LDAP users and groups are reflected on Mediaserver in the next "
        "synchronization cycle")
    new_email = 'absolutely_new_email@example.com'
    ldap_server.change_user_email(generated_ldap_user.uid, new_email)
    ldap_server.add_user_to_group(generated_ldap_user.uid, test_group_name)
    ldap_user_before_change = ldap_user
    [ldap_user] = [u for u in api.list_users() if u.is_ldap]
    assert ldap_user.email == generated_ldap_user.email, (
        f"Expected {generated_ldap_user.email} for user {ldap_user.uid}, but got {ldap_user.email}")
    assert ldap_user.group_ids == ldap_user_before_change.group_ids, (
        f"Assigned groups must remain unchanged before synchronization. Current group IDs: {ldap_user.group_ids}")
    api.sync_ldap_users()
    [ldap_user] = [u for u in api.list_users() if u.is_ldap]
    assert ldap_user.email == new_email, (
        f"Expected {new_email} for user {ldap_user.uid}, but got {ldap_user.email}")
    assert ldap_user.is_enabled
    assigned_group_ids = ldap_user.group_ids - ldap_user_before_change.group_ids
    assert len(assigned_group_ids) == 1, (
        f"Only one group should be assigned, but {assigned_group_ids} are assigned. Current "
        f"assigned group IDs: {ldap_user.group_ids}")
    ldap_groups = {g.name for g in api.list_user_groups() if g.is_ldap}
    assert len(ldap_groups) == 2, (
        f"The expected count of LDAP groups has not changed. Current groups: {ldap_groups}")


_logger = logging.getLogger(__name__)
