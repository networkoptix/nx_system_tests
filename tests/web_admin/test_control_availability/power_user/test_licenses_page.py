# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import Groups
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._licenses import LicensesForm
from tests.web_admin._licenses import get_active_keys_by_rows
from tests.web_admin._licenses import get_active_keys_names_first
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from vm.networks import setup_flat_network


class test_ubuntu22(WebAdminTest):
    """Test pages control availability.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122526
    """

    def _run(self, args, exit_stack: ExitStack):
        _test_pages_control_availability(args, 'ubuntu22', exit_stack)


def _test_pages_control_availability(args, one_vm_type: str, exit_stack: ExitStack):
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_not_older_than('vms_6.0', "This test is only for VMS 6.0+")
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
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
    brand = mediaserver_api.get_brand()
    permanent_professional_key = license_server.generate(
        {'QUANTITY2': 1, 'CLASS2': 'digital', 'BRAND2': brand})
    mediaserver_api.activate_license(permanent_professional_key)
    power_user_name = "power_user"
    power_user_password = "power_user_password"
    mediaserver_api.add_local_user(
        power_user_name, power_user_password, group_id=Groups.POWER_USERS)
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(power_user_name)
    login_form.get_password_field().put(power_user_password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_licenses_link().invoke()
    _ensure_presence_of_license_button(browser)
    _ensure_presence_of_free_license_block(browser)
    licenses = LicensesForm(browser)
    assert len(licenses.get_channels_summary()) == 1
    if distrib.newer_than('vms_6.0'):
        # TODO: Remove try/except clause after WebAdmin version is bumped after the MR
        #  mentioned below and disappearance of 6.1 builds containing older WebAdmin versions.
        #  The exact removal date is unpredictable due to asynchronous nature of WebAdmin updates.
        try:
            [single_server_keys] = get_active_keys_by_rows(browser).values()
        except ValueError as err:
            if 'invalid literal for int() with base 10' in str(err):
                _logger.warning(
                    "Observed obsoleted behavior on VMS 6.1 due to "
                    "https://gitlab.nxvms.dev/dev/cloud_portal/-/merge_requests/8566")
                [single_server_keys] = get_active_keys_names_first(browser).values()
            else:
                raise
    else:
        [single_server_keys] = get_active_keys_names_first(browser).values()
    [key] = single_server_keys
    assert key.value == permanent_professional_key


def _ensure_presence_of_license_button(browser: Browser):
    browser.wait_element(ByXPATH("//nx-block//button[text() = 'Activate']"), 10)


def _ensure_presence_of_free_license_block(browser: Browser):
    selector = ByXPATH("//nx-block//button[text() = 'Activate Free License']")
    browser.wait_element(selector, 10)


_logger = logging.getLogger(__file__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_ubuntu22()]))
