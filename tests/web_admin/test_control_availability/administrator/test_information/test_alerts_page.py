# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome import ChromeConfiguration
from browser.chrome import RemoteChromeDownloadDirectory
from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import StaleElementReference
from directories import get_run_dir
from distrib import BranchNotSupported
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._alerts_page import AlertsList
from tests.web_admin._alerts_page import get_network_interfaces_card
from tests.web_admin._alerts_page import get_servers_alerts_card
from tests.web_admin._alerts_page import get_storage_locations_card
from tests.web_admin._collect_version import collect_version
from tests.web_admin._information_menu import InformationMenu
from tests.web_admin._information_menu import get_download_report_link
from tests.web_admin._information_menu import get_reload_page_link
from tests.web_admin._information_report import get_single_report_data
from tests.web_admin._login import LoginForm
from tests.web_admin._upper_menu import UpperMenu
from vm.networks import setup_flat_network


class test_alerts_page(WebAdminTest):
    """Test pages control availability.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122513
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    """Covers part of the step 7 from the case."""
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    distrib = installer_supplier.distrib()
    if distrib.older_than('vms_6.0'):
        raise BranchNotSupported("This test is only for VMS 6.0+")
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    one_vm_type = 'ubuntu22'
    first_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    second_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    browser_stand_vm = browser_stand.vm()
    [[first_mediaserver_ip, _, _], _] = setup_flat_network(
        [first_stand.vm(), second_stand.vm(), browser_stand_vm],
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
    first_server_name = "first_server"
    second_server_name = "second_server"
    first_api.rename_server(first_server_name)
    second_api.rename_server(second_server_name)
    merge_systems(first_mediaserver, second_mediaserver, take_remote_settings=False)
    browser_downloads_path = browser_stand_vm.os_access.tmp() / 'health_report'
    browser_downloads_path.mkdir()
    chrome_download_directory = RemoteChromeDownloadDirectory(browser_downloads_path)
    chrome_configuration = ChromeConfiguration()
    chrome_download_directory.apply_to(chrome_configuration)
    browser = exit_stack.enter_context(browser_stand.browser(chrome_configuration))
    collect_version(browser, first_mediaserver.url(first_mediaserver_ip))
    browser.open(first_mediaserver.url(first_mediaserver_ip))
    local_administrator_credentials = first_api.get_credentials()
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    UpperMenu(browser).get_information_link().invoke()
    information_left_menu = InformationMenu(browser)
    information_left_menu.get_alerts_link().invoke()
    # An assumption is made that on a clean test system only two server warnings are present
    # according to logger configuration.
    assert information_left_menu.get_active_alerts_count() == 2
    alerts_card = get_servers_alerts_card(browser)
    assert alerts_card.offline == 0
    assert alerts_card.warnings == 2
    storages_location_card = get_storage_locations_card(browser)
    assert storages_location_card.warnings == storages_location_card.errors == 0
    network_interfaces_card = get_network_interfaces_card(browser)
    assert network_interfaces_card.warnings == network_interfaces_card.errors == 0
    alarm_description = 'Logging level is Verbose. Recommended Logging level is Info'

    alerts = AlertsList(browser)
    alerts.get_server_filter_button().invoke()
    alerts.get_server_filters()[first_server_name].apply()
    [first_server_active_alarm] = alerts.get_active_alerts()
    assert alarm_description in first_server_active_alarm.description
    assert first_server_active_alarm.server_name == first_server_name
    assert first_server_active_alarm.type == 'Server'
    assert alerts.clear_filter_button().is_active()
    alerts.get_server_filter_button().invoke()
    alerts.get_server_filters()[second_server_name].apply()
    [second_server_active_alarm] = alerts.get_active_alerts()
    assert alarm_description in second_server_active_alarm.description
    assert second_server_active_alarm.server_name == second_server_name
    assert second_server_active_alarm.type == 'Server'
    assert alerts.clear_filter_button().is_active()
    alerts.get_server_filter_button().invoke()
    alerts.get_server_filters()['All Servers'].apply()
    [active_alarm_a, active_alarm_b] = alerts.get_active_alerts()
    assert alarm_description in active_alarm_a.description
    assert active_alarm_a.server_name in {first_server_name, second_server_name}
    assert active_alarm_a.type == active_alarm_b.type == 'Server'
    assert alarm_description in active_alarm_b.description
    assert active_alarm_b.server_name in {first_server_name, second_server_name}

    alerts.get_devices_filter_button().invoke()
    alerts.get_devices_filters()['Server'].apply()
    [active_alarm_a, active_alarm_b] = alerts.get_active_alerts()
    assert alarm_description in active_alarm_a.description
    assert active_alarm_a.server_name in {first_server_name, second_server_name}
    assert active_alarm_a.type == active_alarm_b.type == 'Server'
    assert alarm_description in active_alarm_b.description
    assert active_alarm_b.server_name in {first_server_name, second_server_name}
    alerts.get_devices_filter_button().invoke()
    alerts.get_devices_filters()['Storages'].apply()
    assert not alerts.get_active_alerts()
    alerts.get_devices_filter_button().invoke()
    alerts.get_devices_filters()['Interface'].apply()
    assert not alerts.get_active_alerts()
    alerts.get_devices_filter_button().invoke()
    alerts.get_devices_filters()['All Device Types'].apply()
    [active_alarm_a, active_alarm_b] = alerts.get_active_alerts()
    assert alarm_description in active_alarm_a.description
    assert active_alarm_a.server_name in {first_server_name, second_server_name}
    assert active_alarm_a.type == active_alarm_b.type == 'Server'
    assert alarm_description in active_alarm_b.description
    assert active_alarm_b.server_name in {first_server_name, second_server_name}

    alerts.get_severity_filter_button().invoke()
    alerts.get_severities_filters()['Only Warnings'].apply()
    [active_alarm_a, active_alarm_b] = alerts.get_active_alerts()
    assert alarm_description in active_alarm_a.description
    assert active_alarm_a.server_name in {first_server_name, second_server_name}
    assert active_alarm_a.type == active_alarm_b.type == 'Server'
    assert alarm_description in active_alarm_b.description
    assert active_alarm_b.server_name in {first_server_name, second_server_name}
    alerts.get_severity_filter_button().invoke()
    alerts.get_severities_filters()['Only Errors'].apply()
    assert not alerts.get_active_alerts()
    alerts.get_severity_filter_button().invoke()
    alerts.get_severities_filters()['All Alerts'].apply()
    [active_alarm_a, active_alarm_b] = alerts.get_active_alerts()
    assert alarm_description in active_alarm_a.description
    assert active_alarm_a.server_name in {first_server_name, second_server_name}
    assert active_alarm_a.type == active_alarm_b.type == 'Server'
    assert alarm_description in active_alarm_b.description
    assert active_alarm_b.server_name in {first_server_name, second_server_name}

    get_download_report_link(browser).invoke()
    # After a link invocation, the diagnostic report is not always constructed
    # and retrieved before the test attempts to find it.
    report_bytes = get_single_report_data(chrome_download_directory, timeout=10)
    (get_run_dir() / 'health_report.json').write_bytes(report_bytes)
    # The testcase does not specify that report should be validated.
    # So far, just assume that the report is a valid non-empty json file.
    assert json.loads(report_bytes), f"Empty JSON received: {report_bytes}"
    reload_page_link = get_reload_page_link(browser)
    reload_page_link.invoke()
    try:
        reload_page_link.invoke()
    except StaleElementReference:
        _logger.info("Page reloaded successfully")


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_alerts_page()]))
