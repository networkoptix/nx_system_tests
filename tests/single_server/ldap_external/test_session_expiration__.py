# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from _internal.ldap_credentials import OPENLDAP_FT_USER_SETTINGS
from _internal.ldap_credentials import OPENLDAP_SETTINGS
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from mediaserver_api import MediaserverApi
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from os_access.ldap import change_ldap_user_password
from tests.single_server.ldap_external.common import set_ldap_settings


def _set_ldap_password_expiration_period(api: MediaserverApi, period_sec: int, api_version: str):
    if not api.server_older_than('vms_6.0') and api_version in ('v0', 'v1', 'v2'):
        # Starting with 6.0, only APIv3 can be used to configure LDAP settings.
        api_v3 = api.with_version(version_cls=MediaserverApiV3)
        api_v3.set_ldap_password_expiration_period(period_sec)
    else:
        api.set_ldap_password_expiration_period(period_sec)


def _test_session_expiration(distrib_url, one_vm_type, api_version, exit_stack):
    installer_supplier = ClassicInstallerSupplier(distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_specific_feature_not_higher_than('ldap_support', 1)
    pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
    one_mediaserver = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    one_mediaserver.mediaserver().start()
    one_mediaserver.mediaserver().api.setup_local_system()
    mediaserver = one_mediaserver.mediaserver()
    api = one_mediaserver.api()
    ldap_host = OPENLDAP_SETTINGS['host']
    mediaserver.os_access.cache_dns_in_etc_hosts([ldap_host])
    mediaserver.allow_ldap_server_access(ldap_host)
    set_ldap_settings(api, OPENLDAP_SETTINGS, api_version=api_version)
    # For APIv3, changing the LDAP settings causes them to be tested immediately. Thus setting
    # the expiration period should be done when all settings and access are configured.
    expiration_period_sec = 3
    _set_ldap_password_expiration_period(api, expiration_period_sec, api_version=api_version)
    # Reset LDAP user password to default.
    change_ldap_user_password(
        user_dn=OPENLDAP_FT_USER_SETTINGS['dn'],
        new_password=OPENLDAP_FT_USER_SETTINGS['password'],
        admin_dn=OPENLDAP_SETTINGS['admin_dn'],
        admin_password=OPENLDAP_SETTINGS['admin_password'],
        ldap_host=ldap_host)
    api.import_single_ldap_user(OPENLDAP_FT_USER_SETTINGS['name'], **OPENLDAP_SETTINGS)
    ldap_user_api = api.with_credentials(
        OPENLDAP_FT_USER_SETTINGS['name'], OPENLDAP_FT_USER_SETTINGS['password'])
    ldap_user_api.disable_auth_refresh()
    assert ldap_user_api.credentials_work()
    time.sleep(expiration_period_sec)
    assert ldap_user_api.credentials_work()
    mediaserver.block_ldap_server_access(ldap_host)
    assert ldap_user_api.credentials_work()
    time.sleep(expiration_period_sec)
    assert not ldap_user_api.credentials_work()
    mediaserver.os_access.cache_dns_in_etc_hosts([ldap_host])
    mediaserver.allow_ldap_server_access(ldap_host)
    ldap_user_api.enable_auth_refresh()
    assert ldap_user_api.credentials_work()
    ldap_user_api.disable_auth_refresh()
    change_ldap_user_password(
        user_dn=OPENLDAP_FT_USER_SETTINGS['dn'],
        new_password='WrongUserPassword',
        admin_dn=OPENLDAP_SETTINGS['admin_dn'],
        admin_password=OPENLDAP_SETTINGS['admin_password'],
        ldap_host=ldap_host)
    assert ldap_user_api.credentials_work()
    time.sleep(expiration_period_sec)
    assert not ldap_user_api.credentials_work()
