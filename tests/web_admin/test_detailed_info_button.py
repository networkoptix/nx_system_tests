# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import StaleElementReference
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import MediaserverApiV2
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._information_menu import InformationMenu
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._servers import ServerSettings
from tests.web_admin._servers import get_servers
from tests.web_admin._servers_health_info_page import get_server_card
from tests.web_admin._upper_menu import UpperMenu
from vm.networks import setup_flat_network


class test_detailed_info_button(WebAdminTest):
    """Detailed Info button.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84274
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
    first_api: MediaserverApiV2 = first_stand.api()
    first_mediaserver = first_stand.mediaserver()
    second_api: MediaserverApiV2 = second_stand.api()
    second_mediaserver = second_stand.mediaserver()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    first_mediaserver.start()
    second_mediaserver.start()
    upload_web_admin_to_mediaserver(first_api, args.webadmin_url)
    license_server_url = license_server.url()
    first_api.setup_local_system({'licenseServer': license_server_url})
    second_api.setup_local_system({'licenseServer': license_server_url})
    first_server_name = "first_server"
    second_server_name = "second_server"
    first_api.rename_server(first_server_name)
    second_api.rename_server(second_server_name)
    merge_systems(first_mediaserver, second_mediaserver, take_remote_settings=False)
    local_administrator_credentials = first_api.get_credentials()
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, first_mediaserver.url(first_mediaserver_ip))
    browser.open(first_mediaserver.url(first_mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    main_menu = MainMenu(browser)
    upper_menu = UpperMenu(browser)
    main_menu.get_servers_link().invoke()
    first_server_entry = get_servers(browser)[first_server_name]
    first_server_entry.is_opened()
    ServerSettings(browser).get_detailed_info_button().invoke()
    assert InformationMenu(browser).get_servers_link().is_selected()
    assert '/health/servers' in browser.get_current_url()
    server_card = get_server_card(browser)
    current_server_name = server_card.get_server_name()
    assert current_server_name == first_server_name, (
        f"{current_server_name!r} != {first_server_name!r}"
        )
    try:
        upper_menu.get_settings_link().invoke()
    except StaleElementReference:
        if installer_supplier.distrib().newer_than('vms_5.1'):
            raise
        # The upper menu may be re-drawn in ~2% cases. Is not reproducible manually.
        upper_menu.get_settings_link().invoke()
    main_menu.get_servers_link().invoke()
    second_server_entry = get_servers(browser)[second_server_name]
    second_server_entry.open()
    ServerSettings(browser).get_detailed_info_button().invoke()
    assert InformationMenu(browser).get_servers_link().is_selected()
    assert '/health/servers' in browser.get_current_url()
    server_card = get_server_card(browser)
    current_server_name = server_card.get_server_name()
    assert current_server_name == second_server_name, (
        f"{current_server_name!r} != {second_server_name!r}"
        )


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_detailed_info_button()]))
