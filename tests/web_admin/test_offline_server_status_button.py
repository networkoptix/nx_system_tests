# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import ElementNotFound
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._interface_wait import assert_elements_absence
from tests.web_admin._interface_wait import element_is_present
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._servers import ServerSettings
from tests.web_admin._servers import get_servers
from vm.networks import setup_flat_network


class test_offline_server_status_button(WebAdminTest):
    """Check Status button.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84275
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    one_vm_type = 'ubuntu22'
    first_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    second_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    [[first_mediaserver_ip, _, _], _] = setup_flat_network(
        [first_stand.vm(), second_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    first_api = first_stand.api()
    first_mediaserver = first_stand.mediaserver()
    second_api = second_stand.api()
    second_mediaserver = second_stand.mediaserver()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    first_mediaserver.start()
    second_mediaserver.start()
    upload_web_admin_to_mediaserver(first_api, args.webadmin_url)
    license_server_url = license_server.url()
    first_api.setup_local_system({'licenseServer': license_server_url})
    second_api.setup_local_system({'licenseServer': license_server_url})
    online_server_name = "online_server"
    offline_server_name = "second_server"
    first_api.rename_server(online_server_name)
    second_api.rename_server(offline_server_name)
    merge_systems(first_mediaserver, second_mediaserver, take_remote_settings=False)
    second_mediaserver.stop()
    local_administrator_credentials = first_api.get_credentials()
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, first_mediaserver.url(first_mediaserver_ip))
    browser.open(first_mediaserver.url(first_mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()

    MainMenu(browser).get_servers_link().invoke()
    server_entries = get_servers(browser)
    server_entries[online_server_name].open()
    online_server_settings = ServerSettings(browser)
    assert_elements_absence(
        online_server_settings.get_server_offline_badge,
        online_server_settings.get_check_status_button,
        )

    server_entries[offline_server_name].open()
    offline_server_settings = ServerSettings(browser)
    assert element_is_present(offline_server_settings.get_server_offline_badge)
    offline_server_settings.get_check_status_button().invoke()
    # It is not possible to reliably catch warning text "Checking..." because it does not appear
    # for a substantial time.
    assert element_is_present(offline_server_settings.get_server_offline_badge)
    assert element_is_present(offline_server_settings.get_check_status_button)

    second_mediaserver.start()
    try:
        _wait_offline_badge_disappearance(offline_server_settings, timeout=30)
    except TimeoutError:
        warning_message = (
            "Possible https://networkoptix.atlassian.net/browse/CLOUD-14812 issue caught. "
            "Attempt to circumvent it by refreshing the page"
            )
        _logger.warning(warning_message)
        browser.refresh()
        assert_elements_absence(
            online_server_settings.get_server_offline_badge,
            online_server_settings.get_check_status_button,
            )


def _wait_offline_badge_disappearance(server_settings: ServerSettings, timeout: float):
    timeout_at = time.monotonic() + timeout
    while True:
        try:
            server_settings.get_server_offline_badge()
        except ElementNotFound:
            return
        if time.monotonic() > timeout_at:
            raise TimeoutError(f"Badge did not disappear after {timeout} sec")
        time.sleep(1)


_logger = logging.getLogger(__file__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_offline_server_status_button()]))
