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
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._nx_apply import NxApplyBar
from tests.web_admin._users import UserCredentialsForm
from tests.web_admin._users import UserForm
from tests.web_admin._users import get_users
from vm.networks import setup_flat_network


class test_users_page(WebAdminTest):
    """Test pages control availability.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122513
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
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
    mediaserver_api = mediaserver_stand.api()
    mediaserver = mediaserver_stand.mediaserver()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    mediaserver.start()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    mediaserver_api.setup_local_system({'licenseServer': license_server.url()})
    local_administrator_credentials = mediaserver_api.get_credentials()
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_users_link().invoke()
    assert not _add_user_button_is_present(browser)
    users = get_users(browser)
    assert set(users.keys()) == {local_administrator_credentials.username}
    admin_entry = users[local_administrator_credentials.username]
    admin_entry.open()
    assert admin_entry.is_opened()
    user_form = UserForm(browser)
    apply_bar = NxApplyBar(browser)
    assert user_form.get_username() == local_administrator_credentials.username
    assert user_form.get_group() == "Administrators"
    user_form.get_name_field().put("IRRELEVANT")
    assert apply_bar.get_save_button().is_active()
    apply_bar.get_cancel_button().invoke()
    user_form.get_email_field().put("irrelevant@irrelevant.irrelevant")
    assert apply_bar.get_save_button().is_active()
    apply_bar.get_cancel_button().invoke()
    user_form.get_change_password().invoke()
    user_credentials = UserCredentialsForm(browser)
    assert user_credentials.get_save_button().is_active()
    user_credentials.get_cancel_button().invoke()


def _add_user_button_is_present(browser: Browser) -> bool:
    try:
        browser.wait_element(ByXPATH("//*[contains(text(),'Add User')]"), 10)
    except ElementNotFound:
        return False
    return True


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_users_page()]))