# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ElementNotFound
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import Groups
from mediaserver_api import MediaserverApiV3
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._nx_apply import NxApplyBar
from tests.web_admin._system_name import SystemNameForm
from tests.web_admin._upper_menu import AccountSettingsMenu
from tests.web_admin._upper_menu import UpperMenu
from tests.web_admin._users import GroupNames
from tests.web_admin._users import UserForm
from tests.web_admin._users import get_available_groups
from tests.web_admin._users import get_users
from vm.networks import setup_flat_network


class test_power_user(WebAdminTest):
    """Administrator can change permission groups for users.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84586
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    # The test is split. Only the step
    # 1) User1 (Power Users)
    # is tested there to ensure better granularity.
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    installer_supplier.distrib().assert_not_older_than('vms_6.0', "This test is only for VMS 6.0+")
    mediaserver_pool = FTMachinePool(installer_supplier, get_run_dir(), 'v3')
    mediaserver_stand = exit_stack.enter_context(mediaserver_pool.one_mediaserver('ubuntu22'))
    mediaserver: Mediaserver = mediaserver_stand.mediaserver()
    mediaserver.start()
    mediaserver_api: MediaserverApiV3 = mediaserver_stand.api()
    mediaserver_api.setup_local_system()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    [[mediaserver_ip, _], _] = setup_flat_network(
        [mediaserver_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    local_user_name = "local_power_user"
    local_user_password = "local_power_user_password"
    mediaserver_api.add_local_user(
        local_user_name, local_user_password, group_id=Groups.POWER_USERS)
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    local_administrator_credentials = mediaserver_api.get_credentials()
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_users_link().invoke()
    user_entry = get_users(browser)[local_user_name]
    user_entry.open()
    power_user_form = UserForm(browser)
    expected_group_name = GroupNames.ADVANCED_VIEWERS
    _change_user_group(browser, from_=GroupNames.POWER_USERS, to=expected_group_name)
    group_name_in_form = power_user_form.get_change_group_button().get_text()
    group_name_in_entry = user_entry.get_current_group_name()
    assert group_name_in_form == group_name_in_entry == expected_group_name, (
        f"{group_name_in_form!r} != {expected_group_name!r} != {group_name_in_form!r}"
        )
    UpperMenu(browser).get_account_settings().invoke()
    AccountSettingsMenu(browser).get_log_out_button().invoke()
    login_form = LoginForm(browser)
    login_field = login_form.get_login_field()
    login_field.clear()
    login_field.put(local_user_name)
    login_form.get_password_field().put(local_user_password)
    login_form.get_submit_button().invoke()
    permissions = SystemNameForm(browser).get_permissions().get_text()
    assert permissions == expected_group_name, f"{permissions!r} != {expected_group_name!r}"


def _change_user_group(browser: Browser, from_: str, to: str):
    # At any click on the menu it is closed and must be reopened.
    UserForm(browser).get_change_group_button().invoke()
    get_available_groups(browser)[from_].invoke()
    UserForm(browser).get_change_group_button().invoke()
    get_available_groups(browser)[to].invoke()
    apply_bar = NxApplyBar(browser)
    apply_bar.get_save_button().invoke()
    try:
        apply_bar.wait_apply()
    except ElementNotFound:
        # Hitting the "Save" button just after it's appearance may do nothing.
        apply_bar.get_save_button().invoke()
        apply_bar.wait_apply()


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_power_user()]))
