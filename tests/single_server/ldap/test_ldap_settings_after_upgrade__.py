# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from contextlib import ExitStack
from typing import Collection
from uuid import UUID

from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from installation import UpdateServer
from installation import find_mediaserver_installation
from mediaserver_api import Groups
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV1
from mediaserver_api import MediaserverApiV2
from mediaserver_api import MediaserverApiV3
from mediaserver_api import Permissions
from mediaserver_api import PermissionsV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.provisioned_mediaservers import LdapServerUnit
from os_access import current_host_address
from os_access.ldap.server_installation import GeneratedLDAPUser
from tests.updates.common import platforms


def _test_ldap_settings_after_upgrade(
        release_distrib_url: str, distrib_url: str, exit_stack: ExitStack):
    mediaserver_os_name = 'ubuntu22'
    ldap_type = 'openldap'
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    installer_supplier.distrib().assert_not_older_than('vms_6.0', "Update tests only supported by VMS 6.0 and newer")
    _logger.info("Prepare a stand with the LDAP server and the old version of Mediaserver")
    installer_supplier_release = ClassicInstallerSupplier(release_distrib_url)
    installer_supplier_release.distrib().assert_can_update_to(installer_supplier.distrib().version())
    pool = FTMachinePool(installer_supplier_release, get_run_dir(), 'v1')
    [ldap_server_unit, mediaserver_unit] = exit_stack.enter_context(
        pool.ldap_vm_and_mediaservers_vm_network([mediaserver_os_name], ldap_type=ldap_type))
    mediaserver = mediaserver_unit.installation()
    mediaserver.disable_update_files_verification()
    mediaserver.start()
    api: MediaserverApiV1 = mediaserver.api
    api.setup_local_system()
    ldap_server = ldap_server_unit.installation()
    _ldap_configure(mediaserver, ldap_server_unit)
    _logger.info("Create users")
    ldap_users = {
        'administrator': _User(GeneratedLDAPUser('Test', 'administrator')),
        'advanced_viewer': _User(GeneratedLDAPUser('Test', 'advanced_viewer')),
        'viewer': _User(GeneratedLDAPUser('Test', 'viewer')),
        'custom_permissions': _User(GeneratedLDAPUser('Test', 'custom_permissions')),
        'role_with_all_permissions': _User(GeneratedLDAPUser('Test', 'role_with_all_permissions')),
        'role_with_no_permissions': _User(GeneratedLDAPUser('Test', 'role_with_no_permissions')),
        'disabled_user': _User(GeneratedLDAPUser('Test', 'disabled_user')),
        'with_digest_auth': _User(GeneratedLDAPUser('Test', 'with_digest_authentication')),
        'with_secure_auth': _User(GeneratedLDAPUser('Test', 'with_secure_authentication')),
        }
    ldap_server.add_users([user.ldap.attrs() for user in ldap_users.values()])
    _ldap_sync(mediaserver)
    users = {u.name: u for u in api.list_users() if u.is_ldap}
    assert len(users) == len(ldap_users), (
        f"Expected {len(ldap_users)} users ({ldap_users.keys()}) from the LDAP server, got "
        f"{len(users)} ({users})")
    for ldap_user in ldap_users.values():
        ldap_user.id = users[ldap_user.uid()].id
        api.enable_user(ldap_user.id)
    api.set_user_permissions(ldap_users['administrator'].id, [Permissions.ADMIN])
    api.set_user_permissions(ldap_users['advanced_viewer'].id, Permissions.ADVANCED_VIEWER_PRESET)
    api.set_user_permissions(ldap_users['viewer'].id, Permissions.VIEWER_PRESET)
    api.set_user_permissions(ldap_users['custom_permissions'].id, [Permissions.VIEW_LOGS])
    role_with_all_permissions_id = api.add_user_group(
        'role_with_all_permissions', [Permissions.ADMIN, *Permissions.NONADMIN_FULL_PRESET])
    api.set_user_group(ldap_users['role_with_all_permissions'].id, role_with_all_permissions_id)
    role_with_no_permissions_id = api.add_user_group('role_with_no_permissions', [Permissions.NO_GLOBAL])
    api.set_user_group(ldap_users['role_with_no_permissions'].id, role_with_no_permissions_id)
    api.disable_user(ldap_users['disabled_user'].id)
    api.switch_basic_and_digest_auth_for_ldap_user(ldap_users['with_digest_auth'].id, True)
    api.switch_basic_and_digest_auth_for_ldap_user(ldap_users['with_secure_auth'].id, False)
    _logger.info("Upgrade the Mediaserver")
    update_archive = installer_supplier.fetch_server_updates([platforms[mediaserver_os_name]])
    update_server = UpdateServer(update_archive, current_host_address())
    exit_stack.enter_context(update_server.serving())
    api.prepare_update(update_server.update_info())
    with api.waiting_for_restart(timeout_sec=120):
        api.install_update()
    _logger.info("Check the LDAP integration after upgrade")
    assert api.get_version() == installer_supplier.distrib().version(), (
        f"Expected {installer_supplier.distrib().version()}, got {api.get_version()}")
    user_after_upgrade = GeneratedLDAPUser('Test', 'user_after_upgrade')
    ldap_server.add_users([user_after_upgrade.attrs()])
    # After the upgrade, some properties (e.g., those retrieved from build_info.txt) have changed.
    # It is necessary to recreate the Mediaserver object.
    mediaserver = find_mediaserver_installation(mediaserver_unit.os_access())
    mediaserver.api = mediaserver_unit.api()
    _ldap_sync(mediaserver)
    # Switch to APIv3 as it provides support for user groups.
    api: MediaserverApiV3 = _api_v3(mediaserver)
    users = {u.id: u for u in api.list_users() if u.is_ldap}
    assert len(users) == len(ldap_users) + 1, (
        f"Expected {len(ldap_users)} users from the LDAP server, got {len(users)}")
    _logger.info("Check groups after upgrade")
    custom_group = api.get_user_group(role_with_all_permissions_id)
    assert custom_group.parent_group_ids == {Groups.POWER_USERS}, (
        "Expected only 'Power Users' group as parent for role_with_all_permissions, but the "
        f"current parents are: {_get_group_names(api, custom_group.parent_group_ids)}")
    assert custom_group.permissions == set(), (
        "Expected no permissions for role_with_all_permissions, but some were found: "
        f"{custom_group.permissions}")
    custom_group = api.get_user_group(role_with_no_permissions_id)
    assert custom_group.parent_group_ids == set(), (
        "Expected no parent groups for role_with_no_permissions, but some were found: "
        f"{_get_group_names(api, custom_group.parent_group_ids)}")
    _logger.info("Check users after upgrade")
    for ldap_user in ldap_users.values():
        assert PermissionsV3.GENERATE_EVENTS in _user_permissions(api, ldap_user.id), (
            f"User {users[ldap_user.id].name}: expected to have the {PermissionsV3.GENERATE_EVENTS} "
            "permission, but it was not found")
    user_id = ldap_users['administrator'].id
    expected_groups = {Groups.LDAP_DEFAULT, Groups.POWER_USERS}
    assert users[user_id].group_ids == expected_groups, (
        f"User {users[user_id].name}: expected {_get_group_names(api, expected_groups)} groups as "
        f"parent, but found: {_get_group_names(api, users[user_id].group_ids)}")
    user_id = ldap_users['advanced_viewer'].id
    expected_groups = {Groups.LDAP_DEFAULT, Groups.ADVANCED_VIEWERS}
    assert users[user_id].group_ids == expected_groups, (
        f"User {users[user_id].name}: expected {_get_group_names(api, expected_groups)} groups as "
        f"parent, but found: {_get_group_names(api, users[user_id].group_ids)}")
    user_id = ldap_users['viewer'].id
    expected_groups = {Groups.LDAP_DEFAULT, Groups.VIEWERS}
    assert users[user_id].group_ids == expected_groups, (
        f"User {users[user_id].name}: expected {_get_group_names(api, expected_groups)} groups as "
        f"parent, but found: {_get_group_names(api, users[user_id].group_ids)}")
    user_id = ldap_users['custom_permissions'].id
    expected_groups = {Groups.LDAP_DEFAULT}
    assert users[user_id].group_ids == expected_groups, (
        f"User {users[user_id].name}: expected {_get_group_names(api, expected_groups)} group as "
        f"parent, but found: {_get_group_names(api, users[user_id].group_ids)}")
    expected_permissions = {PermissionsV3.GENERATE_EVENTS, PermissionsV3.VIEW_LOGS}
    assert users[user_id].permissions == expected_permissions, (
        f"User {users[user_id].name}: expected {expected_permissions} permissions, but found: "
        f"{users[user_id].permissions}")
    user_id = ldap_users['role_with_all_permissions'].id
    expected_groups = {Groups.LDAP_DEFAULT, role_with_all_permissions_id}
    assert expected_groups <= users[user_id].group_ids, (
        f"User {users[user_id].name}: expected {_get_group_names(api, expected_groups)} groups as "
        f"parent, but found: {_get_group_names(api, users[user_id].group_ids)}")
    assert users[user_id].permissions == {PermissionsV3.GENERATE_EVENTS}, (
        f"User {users[user_id].name}: expected {PermissionsV3.GENERATE_EVENTS!r} permission, but "
        f"found: {users[user_id].permissions}")
    user_id = ldap_users['role_with_no_permissions'].id
    expected_groups = {Groups.LDAP_DEFAULT, role_with_no_permissions_id}
    assert expected_groups <= users[user_id].group_ids, (
        f"User {users[user_id].name}: expected {_get_group_names(api, expected_groups)} groups as "
        f"parent, but found: {_get_group_names(api, users[user_id].group_ids)}")
    assert users[user_id].permissions == {PermissionsV3.GENERATE_EVENTS}, (
        f"User {users[user_id].name}: expected {PermissionsV3.GENERATE_EVENTS!r} permission, but "
        f"found: {users[user_id].permissions}")
    user_id = ldap_users['disabled_user'].id
    assert not users[user_id].is_enabled
    user_id = ldap_users['with_digest_auth'].id
    assert users[user_id].is_http_digest_enabled
    user_id = ldap_users['with_secure_auth'].id
    assert not users[user_id].is_http_digest_enabled


class _User:

    def __init__(self, ldap_user: GeneratedLDAPUser):
        self.ldap = ldap_user
        self.id = None

    def uid(self):
        return self.ldap.uid


def _ldap_sync(mediaserver: Mediaserver):
    # The deprecated endpoint api/mergeLdapUsers was removed in VMS 6.0, so APIv3 and
    # rest/v3/ldap/sync should be used instead.
    if mediaserver.older_than('vms_6.0'):
        mediaserver.api.sync_ldap_users()
    else:
        _api_v3(mediaserver).sync_ldap_users()


def _ldap_configure(mediaserver: Mediaserver, ldap_server_unit: LdapServerUnit):
    # API for LDAP integration has some breaking changes in VMS 6.1, so APIv3 should be used.
    if mediaserver.older_than('vms_6.0'):
        api = mediaserver.api
    else:
        api = _api_v3(mediaserver)
    search_base_users = LdapSearchBase(
        base_dn=ldap_server_unit.installation().users_ou(),
        filter='',
        name='users',
        )
    api.set_ldap_settings(
        host=str(ldap_server_unit.subnet_ip()),
        admin_dn=ldap_server_unit.installation().admin_dn(),
        admin_password=ldap_server_unit.installation().password(),
        search_base=[search_base_users],
        )


def _api_v3(mediaserver: Mediaserver) -> MediaserverApiV3:
    auth_handler = mediaserver.api.get_auth_handler()
    api = MediaserverApiV3(mediaserver.base_url())
    api.set_credentials(auth_handler.username, auth_handler.password)
    return api


def _get_group_names(api: MediaserverApiV2, group_ids: Collection[UUID]) -> Collection[str]:
    return {api.get_user_group(group_id).name for group_id in group_ids}


def _user_permissions(api: MediaserverApiV3, user_id: UUID) -> set[str]:
    user = api.get_user(user_id)
    actual_permissions = user.permissions
    for group_id in user.group_ids:
        actual_permissions = actual_permissions.union(api.get_user_group(group_id).permissions)
    return actual_permissions


_logger = logging.getLogger(__name__)
