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
from mediaserver_api import Groups
from mediaserver_api._mediaserver import SettingsPreset
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
    """Security block is hidden for Power User if Security Level is High.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/124000
    """

    def _run(self, args, exit_stack: ExitStack):
        _test_control_availability(args, exit_stack)


def _test_control_availability(args, exit_stack: ExitStack):
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
    first_api.setup_local_system(
        system_settings={'licenseServer': license_server_url},
        settings_preset=SettingsPreset.SECURITY,
        )
    second_api.setup_local_system(
        system_settings={'licenseServer': license_server_url},
        settings_preset=SettingsPreset.SECURITY,
        )
    first_server_name = "first_server"
    second_server_name = "second_server"
    first_api.rename_server(first_server_name)
    second_api.rename_server(second_server_name)
    merge_systems(first_mediaserver, second_mediaserver, take_remote_settings=False)
    power_user_name = "power_user"
    power_user_password = "power_user_password"
    first_api.add_local_user(
        power_user_name, power_user_password, group_id=Groups.POWER_USERS)
    browser_downloads_path = browser_stand_vm.os_access.tmp() / 'health_report'
    browser_downloads_path.mkdir()
    chrome_download_directory = RemoteChromeDownloadDirectory(browser_downloads_path)
    chrome_configuration = ChromeConfiguration()
    chrome_download_directory.apply_to(chrome_configuration)
    browser = exit_stack.enter_context(browser_stand.browser(chrome_configuration))
    collect_version(browser, first_mediaserver.url(first_mediaserver_ip))
    browser.open(first_mediaserver.url(first_mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(power_user_name)
    login_form.get_password_field().put(power_user_password)
    login_form.get_submit_button().invoke()
    UpperMenu(browser).get_information_link().invoke()
    information_left_menu = InformationMenu(browser)
    information_left_menu.get_alerts_link().invoke()
    # An assumption is made that on a clean test system only two server warnings are present
    # according to logger configuration.
    expected_alerts_count = 2
    alerts_count = information_left_menu.get_active_alerts_count()
    assert alerts_count == expected_alerts_count, f"{alerts_count} != {expected_alerts_count}"
    server_alerts_card = get_servers_alerts_card(browser)
    expected_servers_offline = 0
    expected_servers_warnings = 2
    assert server_alerts_card.offline == expected_servers_offline, (
        f"{server_alerts_card.offline} != {expected_servers_offline}"
        )
    assert server_alerts_card.warnings == expected_servers_warnings, (
        f"{server_alerts_card.warnings} != {expected_servers_warnings}"
        )
    storages_location_card = get_storage_locations_card(browser)
    expected_storages_warnings = 0
    expected_storages_errors = 0
    assert storages_location_card.warnings == expected_storages_warnings, (
        f"{storages_location_card.warnings} != {expected_storages_warnings}"
        )
    assert storages_location_card.errors == expected_storages_errors, (
        f"{storages_location_card.errors} != {expected_storages_errors}"
        )
    network_interfaces_card = get_network_interfaces_card(browser)
    expected_interfaces_warnings = 0
    expected_interfaces_errors = 0
    assert network_interfaces_card.warnings == expected_interfaces_warnings, (
        f"{network_interfaces_card.warnings} != {expected_interfaces_warnings}"
        )
    assert network_interfaces_card.errors == expected_interfaces_errors, (
        f"{network_interfaces_card.errors} != {expected_interfaces_errors}"
        )
    alarm_description = 'Logging level is Verbose. Recommended Logging level is Info'
    alerts = AlertsList(browser)
    alerts.get_server_filter_button().invoke()
    alerts.get_server_filters()[first_server_name].apply()
    [first_server_active_alarm] = alerts.get_active_alerts()
    assert alarm_description in first_server_active_alarm.description, (
        f"{alarm_description!r} not in {first_server_active_alarm.description!r}"
        )
    assert first_server_active_alarm.server_name == first_server_name, (
        f"{first_server_active_alarm.server_name!r} != {first_server_name!r}"
        )
    server_alarm_type = 'Server'
    assert first_server_active_alarm.type == server_alarm_type, (
        f"{first_server_active_alarm.type!r} != {server_alarm_type!r}"
        )
    assert alerts.clear_filter_button().is_active()
    alerts.get_server_filter_button().invoke()
    alerts.get_server_filters()[second_server_name].apply()
    [second_server_active_alarm] = alerts.get_active_alerts()
    assert alarm_description in second_server_active_alarm.description, (
        f"{alarm_description!r} not in {second_server_active_alarm.description!r}"
        )
    assert second_server_active_alarm.server_name == second_server_name, (
        f"{second_server_active_alarm.server_name!r} != {second_server_name!r}"
        )
    assert second_server_active_alarm.type == server_alarm_type, (
        f"{second_server_active_alarm.type!r} != {server_alarm_type!r}"
        )
    assert alerts.clear_filter_button().is_active()
    alerts.get_server_filter_button().invoke()
    alerts.get_server_filters()['All Servers'].apply()
    [active_alarm_a, active_alarm_b] = alerts.get_active_alerts()
    assert alarm_description in active_alarm_a.description, (
        f"{alarm_description!r} not in {active_alarm_a.description!r}"
        )
    server_names = {first_server_name, second_server_name}
    assert active_alarm_a.server_name in server_names, (
        f"{active_alarm_a.server_name!r} not in {server_names}"
        )
    assert active_alarm_a.type == server_alarm_type, (
        f"{active_alarm_a.type!r} != {server_alarm_type!r}"
        )
    assert active_alarm_b.type == server_alarm_type, (
        f"{active_alarm_b.type!r} != {server_alarm_type!r}"
        )
    assert alarm_description in active_alarm_b.description, (
        f"{alarm_description!r} not in {active_alarm_b.description!r}"
        )
    assert active_alarm_b.server_name in server_names, (
        f"{active_alarm_b.server_name!r} not in {server_names}"
        )
    alerts.get_devices_filter_button().invoke()
    alerts.get_devices_filters()['Server'].apply()
    [active_alarm_a, active_alarm_b] = alerts.get_active_alerts()
    assert alarm_description in active_alarm_a.description, (
        f"{alarm_description!r} not in {active_alarm_a.description!r}"
        )
    assert active_alarm_a.server_name in server_names, (
        f"{active_alarm_a.server_name!r} not in {server_names}"
        )
    assert active_alarm_a.type == server_alarm_type, (
        f"{active_alarm_a.type!r} != {server_alarm_type!r}"
        )
    assert active_alarm_b.type == server_alarm_type, (
        f"{active_alarm_b.type!r} != {server_alarm_type!r}"
        )
    assert alarm_description in active_alarm_b.description, (
        f"{alarm_description!r} not in {active_alarm_b.description!r}"
        )
    assert active_alarm_b.server_name in server_names, (
        f"{active_alarm_b.server_name!r} not in {server_names}"
        )
    alerts.get_devices_filter_button().invoke()
    alerts.get_devices_filters()['Storages'].apply()
    active_alerts = alerts.get_active_alerts()
    assert not active_alerts, f"Active alerts are found {active_alerts}"
    alerts.get_devices_filter_button().invoke()
    alerts.get_devices_filters()['Interface'].apply()
    active_alerts = alerts.get_active_alerts()
    assert not active_alerts, f"Active alerts are found {active_alerts}"
    alerts.get_devices_filter_button().invoke()
    alerts.get_devices_filters()['All Device Types'].apply()
    [active_alarm_a, active_alarm_b] = alerts.get_active_alerts()
    assert alarm_description in active_alarm_a.description, (
        f"{alarm_description!r} not in {active_alarm_a.description!r}"
        )
    assert active_alarm_a.server_name in server_names, (
        f"{active_alarm_a.server_name!r} not in {server_names}"
        )
    assert active_alarm_a.type == server_alarm_type, (
        f"{active_alarm_a.type!r} != {server_alarm_type!r}"
        )
    assert active_alarm_b.type == server_alarm_type, (
        f"{active_alarm_b.type!r} != {server_alarm_type!r}"
        )
    assert alarm_description in active_alarm_b.description, (
        f"{alarm_description!r} not in {active_alarm_b.description!r}"
        )
    assert active_alarm_b.server_name in server_names, (
        f"{active_alarm_b.server_name!r} not in {server_names}"
        )
    alerts.get_severity_filter_button().invoke()
    alerts.get_severities_filters()['Only Warnings'].apply()
    [active_alarm_a, active_alarm_b] = alerts.get_active_alerts()
    assert alarm_description in active_alarm_a.description, (
        f"{alarm_description!r} not in {active_alarm_a.description!r}"
        )
    assert active_alarm_a.server_name in server_names, (
        f"{active_alarm_a.server_name!r} not in {server_names}"
        )
    assert active_alarm_a.type == server_alarm_type, (
        f"{active_alarm_a.type!r} != {server_alarm_type!r}"
        )
    assert active_alarm_b.type == server_alarm_type, (
        f"{active_alarm_b.type!r} != {server_alarm_type!r}"
        )
    assert alarm_description in active_alarm_b.description, (
        f"{alarm_description!r} not in {active_alarm_b.description!r}"
        )
    assert active_alarm_b.server_name in server_names, (
        f"{active_alarm_b.server_name!r} not in {server_names}"
        )
    alerts.get_severity_filter_button().invoke()
    alerts.get_severities_filters()['Only Errors'].apply()
    active_alerts = alerts.get_active_alerts()
    assert not active_alerts, f"Active alerts are found {active_alerts}"
    alerts.get_severity_filter_button().invoke()
    alerts.get_severities_filters()['All Alerts'].apply()
    [active_alarm_a, active_alarm_b] = alerts.get_active_alerts()
    assert alarm_description in active_alarm_a.description, (
        f"{alarm_description!r} not in {active_alarm_a.description!r}"
        )
    assert active_alarm_a.server_name in server_names, (
        f"{active_alarm_a.server_name!r} not in {server_names}"
        )
    assert active_alarm_a.type == server_alarm_type, (
        f"{active_alarm_a.type!r} != {server_alarm_type!r}"
        )
    assert active_alarm_b.type == server_alarm_type, (
        f"{active_alarm_b.type!r} != {server_alarm_type!r}"
        )
    assert alarm_description in active_alarm_b.description, (
        f"{alarm_description!r} not in {active_alarm_b.description!r}"
        )
    assert active_alarm_b.server_name in server_names, (
        f"{active_alarm_b.server_name!r} not in {server_names}"
        )
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
