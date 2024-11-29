# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from directories import get_run_dir
from distrib import BranchNotSupported
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import Groups
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._information_menu import InformationMenu
from tests.web_admin._login import LoginForm
from tests.web_admin._storages_info_page import StoragesInfoTable
from tests.web_admin._storages_info_page import get_storage_search_input
from tests.web_admin._upper_menu import UpperMenu
from vm.networks import setup_flat_network


class test_storage_locations_info(WebAdminTest):
    """Test pages control availability.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122526
    """

    def _run(self, args, exit_stack: ExitStack):
        _test_pages_control_availability(args, 'ubuntu22', exit_stack)


def _test_pages_control_availability(args, one_vm_type: str, exit_stack: ExitStack):
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    if installer_supplier.distrib().older_than('vms_6.0'):
        raise BranchNotSupported("This test is only for VMS 6.0+")
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
    first_api.setup_local_system({'licenseServer': license_server_url})
    second_api.setup_local_system({'licenseServer': license_server_url})
    first_server_name = "first_server"
    second_server_name = "second_server"
    system_name = "NXSystem"
    first_api.rename_server(first_server_name)
    second_api.rename_server(second_server_name)
    merge_systems(first_mediaserver, second_mediaserver, take_remote_settings=False)
    first_api.rename_site(system_name)
    power_user_name = "power_user"
    power_user_password = "power_user_password"
    first_api.add_local_user(power_user_name, power_user_password, group_id=Groups.POWER_USERS)
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, first_mediaserver.url(first_mediaserver_ip))
    browser.open(first_mediaserver.url(first_mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(power_user_name)
    login_form.get_password_field().put(power_user_password)
    login_form.get_submit_button().invoke()
    UpperMenu(browser).get_information_link().invoke()
    InformationMenu(browser).get_storages_link().invoke()
    info_table = StoragesInfoTable(browser)

    order = info_table.name_order()
    order.set_ascending()
    assert browser.get_current_url().endswith("sortBy=_,name,ASC")
    order.set_descending()
    assert browser.get_current_url().endswith("sortBy=_,name,DESC")

    order = info_table.server_order()
    order.set_ascending()
    assert browser.get_current_url().endswith("sortBy=info,server,ASC")
    order.set_descending()
    assert browser.get_current_url().endswith("sortBy=info,server,DESC")

    order = info_table.type_order()
    order.set_ascending()
    assert browser.get_current_url().endswith("sortBy=info,type,ASC")
    order.set_descending()
    assert browser.get_current_url().endswith("sortBy=info,type,DESC")

    order = info_table.issues_order()
    order.set_ascending()
    assert browser.get_current_url().endswith("sortBy=state,issues24h,ASC")
    order.set_descending()
    assert browser.get_current_url().endswith("sortBy=state,issues24h,DESC")

    order = info_table.read_rate_order()
    order.set_ascending()
    assert browser.get_current_url().endswith("sortBy=activity,readRateBps1m,ASC")
    order.set_descending()
    assert browser.get_current_url().endswith("sortBy=activity,readRateBps1m,DESC")

    order = info_table.write_rate_order()
    order.set_ascending()
    assert browser.get_current_url().endswith("sortBy=activity,writeRateBps1m,ASC")
    order.set_descending()
    assert browser.get_current_url().endswith("sortBy=activity,writeRateBps1m,DESC")

    order = info_table.total_space_order()
    order.set_ascending()
    assert browser.get_current_url().endswith("sortBy=space,totalSpaceB,ASC")
    order.set_descending()
    assert browser.get_current_url().endswith("sortBy=space,totalSpaceB,DESC")

    order = info_table.vms_media_order()
    order.set_ascending()
    assert browser.get_current_url().endswith("sortBy=space,mediaSpaceP,ASC")
    order.set_descending()
    assert browser.get_current_url().endswith("sortBy=space,mediaSpaceP,DESC")

    get_storage_search_input(browser).put("Nonexistent_storage")
    empty_search_xpath = "//nx-system-metrics-component//div[contains(text(), 'Nothing found')]"
    browser.wait_element(ByXPATH(empty_search_xpath), 10)
    _ensure_filter_is_empty(browser)


def _ensure_filter_is_empty(browser: Browser):
    empty_search_xpath = "//nx-system-metrics-component//div[contains(text(), 'Nothing found')]"
    browser.wait_element(ByXPATH(empty_search_xpath), 10)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_storage_locations_info()]))
