# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._licenses import LicensesForm
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from vm.networks import setup_flat_network


class test_activate_single_server_license(WebAdminTest):
    """Test activate license.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/79737
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    license_server = LocalLicenseServer()
    supplier = ClassicInstallerSupplier(args.distrib_url)
    pool = FTMachinePool(supplier, get_run_dir(), 'v2')
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    exit_stack.enter_context(license_server.serving())
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
    mediaserver_api = mediaserver_stand.api()
    mediaserver = mediaserver_stand.mediaserver()
    mediaserver.start()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    brand = mediaserver_api.get_brand()
    channels_quantity = 4
    license_key = license_server.generate({'QUANTITY2': channels_quantity, 'BRAND2': brand})
    mediaserver_api.setup_local_system({'licenseServer': license_server.url()})
    [[mediaserver_ip, _], _] = setup_flat_network(
        [mediaserver_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    local_administrator_credentials = mediaserver_api.get_credentials()
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    main_menu = MainMenu(browser)
    main_menu.get_licenses_link().invoke()
    licenses_form = LicensesForm(browser)
    licenses_form.get_license_input().put(license_key)
    licenses_form.get_activate_button().invoke()
    browser.refresh()
    licenses_summary = licenses_form.get_channels_summary()
    permanent_channels = licenses_summary["Professional"]
    assert permanent_channels.total == channels_quantity
    assert permanent_channels.available == channels_quantity
    assert permanent_channels.in_use == 0


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_activate_single_server_license()]))
