# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApiV3
from mediaserver_api import ResourceGroups
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access.ldap.server_installation import GeneratedLDAPUser


def _test_change_ldap_user_permissions(distrib_url, one_vm_type, exit_stack):
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
    assert ldap_user.accessible_resources == {}, (
        f"User {ldap_user.name} has accessible resources: {ldap_user.accessible_resources}")
    [camera] = api.add_test_cameras(offset=1, count=1)
    ldap_user_api = api.with_credentials(ldap_user.name, generated_ldap_user.password)
    assert ldap_user_api.get_camera(camera.id) is None, (
        f"User {ldap_user.name} has access to camera: {camera.id}")
    api.set_user_access_rights(ldap_user.id, [ResourceGroups.ALL_DEVICES])
    ldap_user = api.get_user(ldap_user.id)
    assert ldap_user.accessible_resources.keys() == {ResourceGroups.ALL_DEVICES}, (
        f"User {ldap_user.name} must have access to resources: {ResourceGroups.ALL_DEVICES}")
    assert ldap_user_api.get_camera(camera.id) is not None, (
        f"User {ldap_user.name} must have access to camera: {camera.id}")
    api.remove_user(ldap_user.id)
    api.sync_ldap_users()
    [ldap_user] = [u for u in api.list_users() if u.is_ldap]
    assert ldap_user.accessible_resources == {}, (
        f"User {ldap_user.name} must not have access to any resources")
    assert ldap_user_api.get_camera(camera.id) is None, (
        f"User {ldap_user.name} must not have access to any cameras")
