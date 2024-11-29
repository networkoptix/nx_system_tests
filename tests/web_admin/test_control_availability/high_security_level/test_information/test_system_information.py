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
from mediaserver_api._mediaserver import SettingsPreset
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._information_menu import InformationMenu
from tests.web_admin._information_menu import get_download_report_link
from tests.web_admin._information_menu import get_reload_page_link
from tests.web_admin._information_report import get_single_report_data
from tests.web_admin._login import LoginForm
from tests.web_admin._system_information_page import get_system_info_cards_v60
from tests.web_admin._system_information_page import get_system_info_cards_v60x
from tests.web_admin._system_information_page import get_system_info_cards_v61plus
from tests.web_admin._upper_menu import UpperMenu
from vm.networks import setup_flat_network


class test_system_information(WebAdminTest):
    """Test pages control availability.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/124000
    """

    def _run(self, args, exit_stack: ExitStack):
        _test_pages_control_availability(args, exit_stack)


def _test_pages_control_availability(args, exit_stack: ExitStack):
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
    system_name = "NXSystem"
    first_api.rename_server(first_server_name)
    second_api.rename_server(second_server_name)
    merge_systems(first_mediaserver, second_mediaserver, take_remote_settings=False)
    first_api.rename_site(system_name)
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
    InformationMenu(browser).get_systems_link().invoke()
    if distrib.equals('vms_6.0.0'):
        system_info_card = get_system_info_cards_v60(browser)[system_name]
    elif distrib.newer_than('vms_6.0.0') and distrib.older_than('vms_6.1.0'):
        system_info_card = get_system_info_cards_v60x(browser)[system_name]
    else:
        system_info_card = get_system_info_cards_v61plus(browser)[system_name]
        empty_cloud_status = ""
        assert system_info_card.cloud_status == empty_cloud_status, (
            f"{system_info_card.cloud_status} != {empty_cloud_status}"
            )
    expected_servers_count = 2
    assert system_info_card.servers == expected_servers_count, (
        f"{system_info_card.servers} != {expected_servers_count}"
        )
    expected_cameras_channels_count = 0
    assert system_info_card.camera_channels == expected_cameras_channels_count, (
        f"{system_info_card.camera_channels} != {expected_cameras_channels_count}"
        )
    expected_storages_count = 2
    assert system_info_card.storages == expected_storages_count, (
        f"{system_info_card.storages} != {expected_storages_count}"
        )
    expected_users_count = 1
    assert system_info_card.users == expected_users_count, (
        f"{system_info_card.users} != {expected_users_count}"
        )
    expected_system_info_version = str(distrib.version())
    assert system_info_card.version == expected_system_info_version, (
        f"{system_info_card.version} != {expected_system_info_version}"
        )
    empty_cloud_id = ""
    assert system_info_card.cloud_id == empty_cloud_id, (
        f"{system_info_card.cloud_id} != {empty_cloud_id}"
        )
    get_download_report_link(browser).invoke()
    # After a link invocation, the diagnostic report is not always constructed
    # and retrieved before the test attempts to find it.
    report_bytes = get_single_report_data(chrome_download_directory, 10)
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
    exit(run_ft_test(sys.argv, [test_system_information()]))
