# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from uuid import UUID

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import Groups
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV3
from mediaserver_api import PermissionsV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access.ldap.server_installation import GeneratedLDAPUser


def _test(distrib_url, one_vm_type, ldap_type: str, exit_stack):
    _logger.info("Prepare a stand")
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v3plus')
    [ldap_server_unit, mediaserver_unit] = exit_stack.enter_context(
        pool.ldap_vm_and_mediaservers_vm_network([one_vm_type], ldap_type))
    ldap_server = ldap_server_unit.installation()
    api: MediaserverApiV3 = mediaserver_unit.api()
    mediaserver_unit.installation().start()
    api.setup_local_system()
    search_base_users = LdapSearchBase(base_dn=ldap_server.users_ou(), filter='', name='users')
    api.set_ldap_settings(
        host=ldap_server_unit.subnet_ip(),
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        search_base=[search_base_users],
        )
    generated_ldap_user = GeneratedLDAPUser('Test', 'User')
    ldap_server.add_users([generated_ldap_user.attrs()])
    api.sync_ldap_users()
    [ldap_user] = [user for user in api.list_users() if user.is_ldap]
    custom_group_id = api.add_user_group(
        'My custom group', [PermissionsV3.VIEW_METRICS, PermissionsV3.VIEW_LOGS])
    custom_group = api.get_user_group(custom_group_id)
    _logger.info(
        "Add the LDAP user to the 'Advanced Viewers' and %r groups and verify", custom_group.name)
    api.add_user_to_group(ldap_user.id, Groups.ADVANCED_VIEWERS)
    api.add_user_to_group(ldap_user.id, custom_group.id)
    ldap_user = api.get_user(ldap_user.id)
    assert {Groups.ADVANCED_VIEWERS, custom_group_id} <= ldap_user.group_ids, (
        f"User {ldap_user.name}, expected assignment to 'Advanced Viewers' and "
        f"{custom_group.name} groups")
    user_permissions = _user_permissions(api, ldap_user.id)
    advanced_viewers_permissions = api.get_user_group(Groups.ADVANCED_VIEWERS).permissions
    assert advanced_viewers_permissions <= user_permissions and custom_group.permissions <= user_permissions, (
        f"User {ldap_user.name}, expected permissions: {advanced_viewers_permissions!r} "
        f"(Advanced Viewer) and {custom_group.permissions} ({custom_group.name})")
    _logger.info("Sync with LDAP and verify again")
    api.sync_ldap_users()
    ldap_user = api.get_user(ldap_user.id)
    assert {Groups.ADVANCED_VIEWERS, custom_group_id} <= ldap_user.group_ids, (
        f"User {ldap_user.name}, expected assignment to 'Advanced Viewers' and "
        f"{custom_group.name} groups")
    user_permissions = _user_permissions(api, ldap_user.id)
    assert advanced_viewers_permissions <= user_permissions and custom_group.permissions <= user_permissions, (
        f"User {ldap_user.name}, expected permissions: {advanced_viewers_permissions!r} "
        f"(Advanced Viewer) and {custom_group.permissions} ({custom_group.name})")


def _user_permissions(api: MediaserverApiV3, user_id: UUID) -> set[str]:
    user = api.get_user(user_id)
    actual_permissions = user.permissions
    for group_id in user.group_ids:
        actual_permissions = actual_permissions.union(api.get_user_group(group_id).permissions)
    return actual_permissions


_logger = logging.getLogger(__name__)
