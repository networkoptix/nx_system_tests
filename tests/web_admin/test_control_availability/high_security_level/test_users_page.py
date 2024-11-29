# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import Groups
from mediaserver_api import MediaserverApiV2
from mediaserver_api._mediaserver import SettingsPreset
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._interface_wait import element_is_present
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._nx_apply import NxApplyBar
from tests.web_admin._users import GroupNames
from tests.web_admin._users import UserCredentialsForm
from tests.web_admin._users import UserForm
from tests.web_admin._users import get_users
from vm.networks import setup_flat_network


class test_users_page(WebAdminTest):
    """Security block is hidden for Power User if Security Level is High.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/124000
    """

    def _run(self, args, exit_stack: ExitStack):
        _test_control_availability(args, exit_stack)


def _test_control_availability(args, exit_stack: ExitStack):
    """Covers step 4 from the case."""
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    installer_supplier.distrib().assert_not_older_than('vms_6.0', "This test is only for VMS 6.0+")
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    [[mediaserver_ip, _], _] = setup_flat_network(
        [mediaserver_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    mediaserver_api: MediaserverApiV2 = mediaserver_stand.api()
    mediaserver = mediaserver_stand.mediaserver()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    mediaserver.start()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    mediaserver_api.setup_local_system(
        system_settings={'licenseServer': license_server.url()},
        settings_preset=SettingsPreset.SECURITY,
        )
    local_administrator_credentials = mediaserver_api.get_credentials()
    power_user_name = "power_user"
    power_user_password = "power_user_password"
    mediaserver_api.add_local_user(power_user_name, power_user_password, group_id=Groups.POWER_USERS)
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(power_user_name)
    login_form.get_password_field().put(power_user_password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_users_link().invoke()
    assert not _add_user_button_is_present(browser)
    users = get_users(browser)
    assert set(users.keys()) == {power_user_name, local_administrator_credentials.username}
    admin_entry = users[local_administrator_credentials.username]
    user_entry = users[power_user_name]
    admin_entry.open()
    assert admin_entry.is_opened()
    assert not user_entry.is_opened()
    admin_user = UserForm(browser)
    assert admin_user.get_username() == local_administrator_credentials.username
    assert admin_user.get_group() == "Administrators"
    assert not admin_user.get_name_field().is_active()
    assert not admin_user.get_email_field().is_active()
    assert not element_is_present(admin_user.get_change_password)
    user_entry.open()
    assert user_entry.is_opened()
    assert not admin_entry.is_opened()
    user_form = UserForm(browser)
    apply_bar = NxApplyBar(browser)
    assert user_form.get_username() == power_user_name
    assert user_form.get_group() == GroupNames.POWER_USERS
    visible_name = "IRRELEVANT"
    irrelevant_email = "irrelevant@irrelevant.irrelevant"
    user_form.get_name_field().put(visible_name)
    user_form.get_email_field().put(irrelevant_email)
    assert apply_bar.get_cancel_button().is_active()
    apply_bar.get_save_button().invoke()
    apply_bar.wait_apply()
    changed_visible_name = user_form.get_name_field().get_value()
    changed_email = user_form.get_email_field().get_value()
    assert changed_visible_name == visible_name, f"{changed_visible_name!r} != {visible_name!r}"
    assert changed_email == irrelevant_email, f"{changed_email!r} != {irrelevant_email!r}"
    user_form.get_change_password().invoke()
    user_credentials = UserCredentialsForm(browser)
    strong_password = "=-098&^%$#IRRelevant"
    user_credentials.get_current_password_input().put(power_user_password)
    user_credentials.get_new_password_input().put(strong_password)
    user_credentials.get_new_password_confirmation_input().put(strong_password)
    assert user_credentials.get_cancel_button().is_active()
    user_credentials.get_save_button().invoke()
    _wait_password_changed(browser, 10)


def _add_user_button_is_present(browser: Browser) -> bool:
    try:
        browser.wait_element(ByXPATH("//*[contains(text(),'Add User')]"), 10)
    except ElementNotFound:
        return False
    return True


def _wait_password_changed(browser: Browser, timeout: float):
    toast_selector = ByXPATH(
        "//nx-app-toasts//nx-toast[contains(., 'Password successfully changed')]")
    try:
        browser.wait_element(toast_selector, timeout)
    except ElementNotFound:
        raise RuntimeError(f"Password change toast is not found by {toast_selector}")


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_users_page()]))
