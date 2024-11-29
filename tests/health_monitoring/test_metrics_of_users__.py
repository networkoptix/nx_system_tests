# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import MediaserverApiHttpError
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from _internal.ldap_credentials import OPENLDAP_SETTINGS


def _test_users(cloud_host, distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_api_support(api_version, 'ldap_parameters')
    distrib.assert_api_support(api_version, 'users')
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_account = cloud_account_factory.create_account()
    customization_name = distrib.customization().customization_name
    cloud_account.set_user_customization(customization_name)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    mediaserver = one_mediaserver.mediaserver()
    mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *public_ip_check_addresses])
    mediaserver.allow_access_to_cloud(cloud_host)
    mediaserver.set_cloud_host(cloud_host)
    ldap_host = OPENLDAP_SETTINGS['host']
    mediaserver.os_access.cache_dns_in_etc_hosts([ldap_host])
    mediaserver.allow_ldap_server_access(ldap_host)
    mediaserver.start()
    mediaserver.api.setup_cloud_system(cloud_account)
    api = one_mediaserver.api()
    owner_users = mediaserver.api.list_users()
    expected_data = {'owners': len(owner_users)}
    actual_data = {'owners': api.get_metrics('system_info', 'users')}
    second_cloud_account = cloud_account_factory.create_account()
    second_cloud_account.set_user_customization(customization_name)
    created_user_count = create_users(api, second_cloud_account)
    expected_data['after_creation'] = len(owner_users) + created_user_count
    actual_data['after_creation'] = api.get_metrics('system_info', 'users')
    mediaserver.block_ldap_server_access(ldap_host)
    try:
        mediaserver.api.check_ldap_server(**OPENLDAP_SETTINGS)
    except MediaserverApiHttpError as exc:
        if mediaserver.specific_features().get('ldap_support') > 0:
            expected_error = 'can not connect to ldap server.'
        else:
            expected_error = 'invalid ldap settings'
        assert exc.vms_error_string.lower() == expected_error
    else:
        raise RuntimeError("LDAP server is available after disabling access to it")
    expected_data['ldap_disabled'] = len(owner_users) + created_user_count
    actual_data['ldap_disabled'] = api.get_metrics('system_info', 'users')
    mediaserver.os_access.cache_dns_in_etc_hosts([ldap_host])
    mediaserver.allow_ldap_server_access(ldap_host)
    mediaserver.api.check_ldap_server(**OPENLDAP_SETTINGS)
    for user in api.list_users():
        if user in owner_users:
            continue
        api.disable_user(user.id)
    expected_data['users_disabled'] = len(owner_users) + created_user_count
    actual_data['users_disabled'] = api.get_metrics('system_info', 'users')
    for user in api.list_users():
        if user in owner_users:
            continue
        api.remove_user(user.id)
    expected_data['after_deletion'] = len(owner_users)
    actual_data['after_deletion'] = api.get_metrics('system_info', 'users')
    assert actual_data == expected_data


def create_users(mediaserver_api, second_cloud_account):
    mediaserver_api.add_local_admin('test_administrator', '123')
    mediaserver_api.add_local_viewer('test_viewer', '123')
    mediaserver_api.add_local_live_viewer('test_live_viewer', '123')
    mediaserver_api.add_local_advanced_viewer('test_advanced_viewer', '123')
    # Since APIv3, some permissions are marked as deprecated. But they
    # can still be assigned to the groups. Therefore, custom permissions
    # for the user must be assigned using group.
    custom_permissions_group = mediaserver_api.add_user_group(
        'custom_permissions_group',
        Permissions.NONADMIN_FULL_PRESET,
        )
    mediaserver_api.add_local_user(
        'test_custom_permissions',
        '123',
        group_id=custom_permissions_group,
        )
    group_id = mediaserver_api.add_user_group('custom_group', [Permissions.NO_GLOBAL])
    mediaserver_api.add_local_user('test_custom_group', '123', group_id=group_id)
    mediaserver_api.add_cloud_user(
        second_cloud_account.user_email,
        permissions=[Permissions.ADMIN],
        email=second_cloud_account.user_email,
        )
    mediaserver_api.set_ldap_settings(**OPENLDAP_SETTINGS)
    known_user_ids = {user.id for user in mediaserver_api.list_users()}
    # Users will be saved with LIVE_VIEWER permissions and all users will be disabled.
    mediaserver_api.sync_ldap_users()
    # There is a user named 'admin' on the LDAP server. After the synchronization with LDAP,
    # the server has two users with the same name 'admin' - an enabled local user
    # and a disabled LDAP user. It is forbidden for both of them to be in the same state
    # (enabled or disabled).
    # To avoid problems in the test, it is best to remove the LDAP user.
    for user in mediaserver_api.list_users():
        if user.name == 'admin' and user.is_ldap:
            mediaserver_api.remove_user(user.id)
    new_user_ids = {user.id for user in mediaserver_api.list_users()} - known_user_ids
    for user_id in new_user_ids:
        mediaserver_api.enable_user(user_id)
    return len(new_user_ids) + 7  # 6 local users and 1 cloud user
