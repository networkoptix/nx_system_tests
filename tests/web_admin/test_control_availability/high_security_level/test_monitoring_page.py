# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import hashlib
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api._mediaserver import SettingsPreset
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._login import LoginForm
from tests.web_admin._monitoring import SystemLogs
from tests.web_admin._monitoring import get_monitoring_graph
from tests.web_admin._monitoring import get_monitoring_menu
from tests.web_admin._monitoring import get_monitoring_servers
from tests.web_admin._upper_menu import UpperMenu
from vm.networks import setup_flat_network


class test_monitoring_page(WebAdminTest):
    """Test pages control availability.

    Selection-Tag: web-admin-gitlab
    See: https://networkoptix.atlassian.net/browse/CLOUD-12859
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/124000
    """

    def _run(self, args, exit_stack: ExitStack):
        _test_pages_control_availability(args, 'ubuntu22', exit_stack)


def _test_pages_control_availability(args, one_vm_type: str, exit_stack: ExitStack):
    """Covers step 8 from the case."""
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    installer_supplier.distrib().assert_not_older_than('vms_6.0', "This test is only for VMS 6.0+")
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
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
    local_administrator_credentials = first_api.get_credentials()
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, first_mediaserver.url(first_mediaserver_ip))
    browser.open(first_mediaserver.url(first_mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    UpperMenu(browser).get_monitoring_link().invoke()
    monitoring_menu = get_monitoring_menu(browser)

    monitoring_menu.get_server_choice_button().invoke()
    get_monitoring_servers(browser)[first_server_name].invoke()
    monitoring_menu.get_graphs_link().invoke()
    _wait_monitoring_page_update(browser, timeout=10)
    monitoring_menu.get_logs_link().invoke()
    logs_element = SystemLogs(browser)
    main_logger_name = 'MAIN'
    http_logger_name = 'HTTP'
    system_logger_name = 'SYSTEM'
    opened_logger_name = logs_element.get_select_logger_button().get_text()
    assert opened_logger_name == main_logger_name, (
        f"{opened_logger_name!r} != {main_logger_name!r}"
        )
    assert logs_element.get_refresh_logger_button().is_active()
    main_logger_text = logs_element.get_logger_element().get_raw_text()
    logs_element.get_select_logger_button().invoke()
    logs_element.get_loggers()[http_logger_name].invoke()
    opened_logger_name = logs_element.get_select_logger_button().get_text()
    assert opened_logger_name == http_logger_name, (
        f"{opened_logger_name!r} != {http_logger_name!r}"
        )
    assert logs_element.get_refresh_logger_button().is_active()
    # Logger element is mutable and there is no way to ensure its relevance.
    # Generic polling approach could not be used because of single 500 000 chars-long line in logs
    # which drastically increases test time and decreases stability.
    time.sleep(2)
    http_logger_text = logs_element.get_logger_element().get_raw_text()
    logs_element.get_select_logger_button().invoke()
    logs_element.get_loggers()[system_logger_name].invoke()
    opened_logger_name = logs_element.get_select_logger_button().get_text()
    assert opened_logger_name == system_logger_name, (
        f"{opened_logger_name} != {system_logger_name}"
        )
    assert logs_element.get_refresh_logger_button().is_active()
    system_logger_text = logs_element.get_logger_element().get_raw_text()
    assert main_logger_text != http_logger_text, "MAIN logger text is the same as HTTP"
    assert http_logger_text != system_logger_text, "HTTP logger text is the same as SYSTEM"

    monitoring_menu.get_server_choice_button().invoke()
    get_monitoring_servers(browser)[first_server_name].invoke()
    monitoring_menu.get_graphs_link().invoke()
    _wait_monitoring_page_update(browser, timeout=10)
    monitoring_menu.get_logs_link().invoke()
    opened_logger_name = logs_element.get_select_logger_button().get_text()
    assert opened_logger_name == main_logger_name, (
        f"{opened_logger_name!r} != {main_logger_name!r}"
        )
    assert logs_element.get_refresh_logger_button().is_active()
    main_logger_text = logs_element.get_logger_element().get_raw_text()
    logs_element.get_select_logger_button().invoke()
    logs_element.get_loggers()[http_logger_name].invoke()
    opened_logger_name = logs_element.get_select_logger_button().get_text()
    assert opened_logger_name == http_logger_name, (
        f"{opened_logger_name!r} != {http_logger_name!r}"
        )
    assert logs_element.get_refresh_logger_button().is_active()
    # Logger element is mutable and there is no way to ensure its relevance.
    # Generic polling approach could not be used because of single 500 000 chars-long line in logs
    # which drastically increases test time and decreases stability.
    time.sleep(2)
    http_logger_text = logs_element.get_logger_element().get_raw_text()
    logs_element.get_select_logger_button().invoke()
    logs_element.get_loggers()[system_logger_name].invoke()
    opened_logger_name = logs_element.get_select_logger_button().get_text()
    assert opened_logger_name == system_logger_name, (
        f"{opened_logger_name!r} != {system_logger_name!r}"
        )
    assert logs_element.get_refresh_logger_button().is_active()
    system_logger_text = logs_element.get_logger_element().get_raw_text()
    assert main_logger_text != http_logger_text, "MAIN logger text is the same as HTTP"
    assert http_logger_text != system_logger_text, "HTTP logger text is the same as SYSTEM"


def _wait_monitoring_page_update(browser: Browser, timeout: float):
    graph = get_monitoring_graph(browser)
    timeout_at = time.monotonic() + timeout
    lines_hashes = set()
    while True:
        lines = graph.get_lines()
        lines_digest = hashlib.md5(''.join(lines).encode('utf-8')).hexdigest()
        lines_hashes.add(lines_digest)
        if len(lines_hashes) > 1:
            return
        if time.monotonic() > timeout_at:
            raise RuntimeError(f"Monitoring graph is not updated after {timeout}")
        time.sleep(0.3)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_monitoring_page()]))
