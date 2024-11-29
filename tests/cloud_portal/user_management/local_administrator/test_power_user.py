# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ElementNotFound
from browser.webdriver import StaleElementReference
from cloud_api import CloudAccount
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from installation import public_ip_check_addresses
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import Groups
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApi
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.provisioned_mediaservers import LdapMachinePool
from os_access.ldap.server_installation import GeneratedLDAPUser
from os_access.ldap.server_installation import LDAPServerInstallation
from runner.ft_test import run_ft_test
from tests.base_test import CloudTest
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._nx_apply import NxApplyBar
from tests.web_admin._users import DeleteUserModal
from tests.web_admin._users import UserForm
from tests.web_admin._users import get_available_groups
from tests.web_admin._users import get_users
from vm.networks import setup_flat_network


class test_power_user(WebAdminTest, CloudTest):
    """Local Administrator can add/change/remove Power Users.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122736
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    installer_supplier.distrib().assert_not_older_than('vms_6.0', "This test is only for VMS 6.0+")
    cloud_host = args.cloud_host
    ldap_pool = LdapMachinePool(get_run_dir())
    ldap_vm = exit_stack.enter_context(ldap_pool.ldap_vm('openldap'))
    ldap_vm.ensure_started(get_run_dir())
    cloud_account_factory = make_cloud_account_factory(cloud_host)
    cloud_owner: CloudAccount = exit_stack.enter_context(cloud_account_factory.temp_account())
    customization_name = installer_supplier.distrib().customization().customization_name
    cloud_owner.set_user_customization(customization_name)
    services_hosts = cloud_owner.get_services_hosts()
    mediaserver_pool = FTMachinePool(installer_supplier, get_run_dir(), 'v3')
    mediaserver_stand = exit_stack.enter_context(mediaserver_pool.one_mediaserver('ubuntu22'))
    mediaserver: Mediaserver = mediaserver_stand.mediaserver()
    mediaserver.os_access.cache_dns_in_etc_hosts(
        [cloud_host, *services_hosts, *public_ip_check_addresses])
    mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
    mediaserver.set_cloud_host(cloud_host)
    mediaserver.start()
    mediaserver_api: MediaserverApiV3 = mediaserver_stand.api()
    mediaserver_api.setup_local_system()
    system_name = mediaserver_api.get_system_name()
    bind_info = cloud_owner.bind_system(system_name)
    mediaserver_api.connect_system_to_cloud(
        bind_info.auth_key, bind_info.system_id, cloud_owner.user_email)
    system_id = mediaserver_api.get_cloud_system_id()
    cloud_power_user: CloudAccount = exit_stack.enter_context(cloud_account_factory.temp_account())
    cloud_owner.share_system(
        system_id, cloud_power_user.user_email, user_groups=[Groups.POWER_USERS])
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    [[mediaserver_ip, ldap_server_ip, _], _] = setup_flat_network(
        [mediaserver_stand.vm(), ldap_vm, browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    ldap_server: LDAPServerInstallation = exit_stack.enter_context(
        ldap_pool.ldap_server('openldap', ldap_vm))
    ldap_power_user = GeneratedLDAPUser('LDAP', 'PowerUser')
    ldap_server.add_users([ldap_power_user.attrs()])
    group_name = 'Users'
    ldap_server.add_group(group_name, members=[ldap_power_user.uid])
    search_base_users = LdapSearchBase(
        base_dn=ldap_server.users_ou(),
        filter='',
        name='users',
        )
    mediaserver_api.set_ldap_settings(
        host=ldap_server_ip,
        admin_dn=ldap_server.admin_dn(),
        admin_password=ldap_server.password(),
        search_base=[search_base_users],
        )
    mediaserver_api.sync_ldap_users()
    [added_ldap_user] = [user for user in mediaserver_api.list_users() if user.is_ldap]
    mediaserver_api.add_user_to_group(added_ldap_user.id, Groups.POWER_USERS)
    local_power_user_name = "local_power_user"
    local_power_user_password = "local_power_user_password"
    mediaserver_api.add_local_user(
        local_power_user_name, local_power_user_password, group_id=Groups.POWER_USERS)
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    local_administrator_credentials = mediaserver_api.get_credentials()
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    _wait_appearance(cloud_power_user.user_email, mediaserver_api, timeout=20)
    MainMenu(browser).get_users_link().invoke()
    get_users(browser)[local_power_user_name].open()
    _change_power_user_to_advanced_viewer(browser)
    users_by_name = {user.name: user for user in mediaserver_api.list_users()}
    api_local_user_validated = users_by_name[local_power_user_name]
    assert Groups.ADVANCED_VIEWERS in api_local_user_validated.group_ids, (
        f"{Groups.ADVANCED_VIEWERS!r} not in {api_local_user_validated.group_ids}"
        )
    get_users(browser)[local_power_user_name].open()
    UserForm(browser).get_delete_button().invoke()
    DeleteUserModal(browser).get_delete_button().invoke()
    users_names = {user.name for user in mediaserver_api.list_users()}
    assert local_power_user_name not in users_names, (
        f"{local_power_user_name!r} in {users_names!r}"
        )
    get_users(browser)[ldap_power_user.uid].open()
    _change_power_user_to_advanced_viewer(browser)
    users_by_name = {user.name: user for user in mediaserver_api.list_users()}
    api_ldap_user_validated = users_by_name[ldap_power_user.uid]
    assert Groups.ADVANCED_VIEWERS in api_ldap_user_validated.group_ids, (
        f"{Groups.ADVANCED_VIEWERS!r} not in {api_ldap_user_validated.group_ids}"
        )
    get_users(browser)[ldap_power_user.uid].open()
    UserForm(browser).get_delete_button().invoke()
    DeleteUserModal(browser).get_delete_button().invoke()
    users_names = {user.name for user in mediaserver_api.list_users()}
    assert ldap_power_user.uid not in users_names, f"{ldap_power_user.uid!r} in {users_names!r}"
    _wait_user_disappearance(ldap_power_user.uid, browser, timeout=20)
    get_users(browser)[cloud_power_user.user_email].open()
    _change_power_user_to_advanced_viewer(browser)
    users_by_name = {user.name: user for user in mediaserver_api.list_users()}
    api_cloud_user_validated = users_by_name[cloud_power_user.user_email]
    assert Groups.ADVANCED_VIEWERS in api_cloud_user_validated.group_ids, (
        f"{Groups.ADVANCED_VIEWERS!r} not in {api_cloud_user_validated.group_ids}"
        )
    get_users(browser)[cloud_power_user.user_email].open()
    UserForm(browser).get_remove_button().invoke()
    DeleteUserModal(browser).get_delete_button().invoke()
    _wait_disappearance(cloud_power_user.user_email, mediaserver_api, timeout=5)


def _wait_user_disappearance(user_name: str, browser: Browser, timeout: float):
    # It appears that in Chrome of certain versions automatic renewal of the users list
    # is not happening.
    browser.refresh()
    # The menu element is re-drawn after user removal, and it takes some time for a user
    # to disappear from the WebAdmin interface.
    timeout_at = time.monotonic() + timeout
    while True:
        try:
            users = get_users(browser)
        except StaleElementReference:
            continue
        user_names = list(users.keys())
        if user_name not in user_names:
            return
        if time.monotonic() > timeout_at:
            raise RuntimeError(
                f"{user_name!r} is still amongst {user_names} after {timeout} seconds")
        time.sleep(0.3)


def _change_power_user_to_advanced_viewer(browser: Browser):
    # At any click on the menu it is closed and must be reopened.
    UserForm(browser).get_change_group_button().invoke()
    get_available_groups(browser)["Power Users"].invoke()
    UserForm(browser).get_change_group_button().invoke()
    get_available_groups(browser)["Advanced Viewers"].invoke()
    apply_bar = NxApplyBar(browser)
    apply_bar.get_save_button().invoke()
    try:
        apply_bar.wait_apply()
    except ElementNotFound:
        # Hitting the "Save" button just after it's appearance may do nothing.
        apply_bar.get_save_button().invoke()
        apply_bar.wait_apply()


def _wait_appearance(user_name: str, mediaserver_api: MediaserverApi, timeout: float):
    # It takes considerable time for a Cloud user to appear in the users list because the sharing
    # process involves data exchange between a local system and the Cloud portal itself.
    timeout_at = time.monotonic() + timeout
    while True:
        user_names = {user.name for user in mediaserver_api.list_users()}
        if user_name in user_names:
            return
        if time.monotonic() > timeout_at:
            raise RuntimeError(
                f"{user_name!r} is not amongst {user_names} after {timeout} seconds")
        time.sleep(0.3)


def _wait_disappearance(user_name: str, mediaserver_api: MediaserverApi, timeout: float):
    # It takes some time for a Cloud user to disappear from the users list because the user removal
    # process involves data exchange between a local system and the Cloud portal itself.
    timeout_at = time.monotonic() + timeout
    while True:
        user_names = {user.name for user in mediaserver_api.list_users()}
        if user_name not in user_names:
            return
        if time.monotonic() > timeout_at:
            raise RuntimeError(f"{user_name!r} is amongst {user_names} after {timeout} seconds")
        time.sleep(0.3)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_power_user()]))
