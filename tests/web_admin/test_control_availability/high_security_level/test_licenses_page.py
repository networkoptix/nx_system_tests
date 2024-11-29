# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
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
from tests.web_admin._licenses import LicensesForm
from tests.web_admin._licenses import get_active_keys_by_rows
from tests.web_admin._licenses import get_active_keys_names_first
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from vm.networks import setup_flat_network


class test_licenses_page(WebAdminTest):
    """Security block is hidden for Power User if Security Level is High.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/124000
    """

    def _run(self, args, exit_stack: ExitStack):
        _test_control_availability(args, exit_stack)


def _test_control_availability(args, exit_stack: ExitStack):
    """Covers step 2 from the case."""
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_not_older_than('vms_6.0', "This test is only for VMS 6.0+")
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
    brand = mediaserver_api.get_brand()
    permanent_professional_key = license_server.generate(
        {'QUANTITY2': 4, 'CLASS2': 'digital', 'BRAND2': brand})
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
    licenses_form = LicensesForm(browser)
    assert element_is_present(licenses_form.get_license_input)
    assert element_is_present(licenses_form.get_activate_button)
    assert element_is_present(licenses_form.get_activate_free_licenses_button)
    channels_summary = licenses_form.get_channels_summary()
    assert len(channels_summary) == 1, f"Received unexpected channels summary: {channels_summary}"
    if distrib.newer_than('vms_6.0'):
        # TODO: Remove try/except clause after WebAdmin version is bumped after the MR
        #  mentioned below and disappearance of 6.1 builds containing older WebAdmin versions.
        #  The exact removal date is unpredictable due to asynchronous nature of WebAdmin updates.
        try:
            [active_keys] = get_active_keys_by_rows(browser).values()
        except ValueError as err:
            if 'invalid literal for int() with base 10' in str(err):
                _logger.warning(
                    "Observed obsoleted behavior on VMS 6.1 due to "
                    "https://gitlab.nxvms.dev/dev/cloud_portal/-/merge_requests/8566")
                [active_keys] = get_active_keys_names_first(browser).values()
            else:
                raise
    else:
        [active_keys] = get_active_keys_names_first(browser).values()
    assert len(active_keys) == 1, f"Received unexpected keys count: {active_keys}"


_logger = logging.getLogger(__file__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_licenses_page()]))
