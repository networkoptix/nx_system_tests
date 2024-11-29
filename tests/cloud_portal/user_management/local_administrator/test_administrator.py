# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api import CloudAccount
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from installation import public_ip_check_addresses
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import Groups
from mediaserver_api import MediaserverApi
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import CloudTest
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._interface_wait import assert_elements_absence
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._users import AddUserDialog
from tests.web_admin._users import UserForm
from tests.web_admin._users import get_add_user_button
from tests.web_admin._users import get_available_groups
from tests.web_admin._users import get_users
from vm.networks import setup_flat_network


class test_administrator(WebAdminTest, CloudTest):
    """Local Administrators cannot add/edit/remove another Administrators.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/123056
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    installer_supplier.distrib().assert_not_older_than('vms_6.0', "This test is only for VMS 6.0+")
    cloud_host = args.cloud_host
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
    [[mediaserver_ip, _], _] = setup_flat_network(
        [mediaserver_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
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
    _wait_appearance(cloud_power_user.user_email, mediaserver_api, timeout=30)
    MainMenu(browser).get_users_link().invoke()
    get_users(browser)[local_power_user_name].open()
    get_add_user_button(browser).invoke()
    add_user_dialog = AddUserDialog(browser)
    add_user_dialog.get_permission_group_button().invoke()
    available_groups = add_user_dialog.get_permission_group_entries()
    administrators_group_name = "Administrators"
    assert administrators_group_name not in available_groups, (
        f"{administrators_group_name!r} in {available_groups!r}"
        )
    add_user_dialog.get_close_button().invoke()
    available_users = get_users(browser)
    available_users[cloud_owner.user_email].open()
    cloud_user_form = UserForm(browser)
    assert_elements_absence(
        cloud_user_form.get_change_group_button,
        cloud_user_form.get_delete_button,
        )
    available_users[local_power_user_name].open()
    UserForm(browser).get_change_group_button().invoke()
    available_groups = get_available_groups(browser)
    assert administrators_group_name not in available_groups, (
        f"{administrators_group_name!r} in {available_groups!r}"
        )
    available_users[cloud_power_user.user_email].open()
    UserForm(browser).get_change_group_button().invoke()
    available_groups = get_available_groups(browser)
    assert administrators_group_name not in available_groups, (
        f"{administrators_group_name!r} in {available_groups!r}"
        )


def _wait_appearance(user_name: str, mediaserver_api: MediaserverApi, timeout: float):
    # It takes considerable time for a Cloud user to appear in the users list because the sharing
    # process involves data exchange between a local system and Cloud.
    timeout_at = time.monotonic() + timeout
    while True:
        user_names = {user.name for user in mediaserver_api.list_users()}
        if user_name in user_names:
            return
        if time.monotonic() > timeout_at:
            raise RuntimeError(
                f"{user_name!r} is not amongst {user_names} after {timeout} seconds")
        time.sleep(0.3)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_administrator()]))
