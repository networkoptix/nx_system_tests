# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._system_left_menu import UsersDropdown
from tests.cloud_portal._system_users import SystemUsers
from tests.cloud_portal._system_users import UserStatusSwitch
from vm.networks import setup_flat_network


class test_owner_can_disable_enable_user(VMSTest, CloudTest):
    """Test owner can disable and enable a Cloud user.

    Selection-Tag: 63390
    Selection-Tag: cloud_portal
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/63390
    """

    def _run(self, args, exit_stack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        server_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        cloud_owner = cloud_account_factory.create_account()
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_owner.set_user_customization(customization_name)
        services_hosts = cloud_owner.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [server_stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver = server_stand.mediaserver()
        mediaserver.os_access.cache_dns_in_etc_hosts(
            [cloud_host, *services_hosts, *public_ip_check_addresses],
            )
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        mediaserver.start()
        mediaserver.api.setup_cloud_system(cloud_owner)
        cloud_viewer = cloud_account_factory.create_account()
        mediaserver.api.add_cloud_user(
            name=cloud_viewer.user_email,
            email=cloud_viewer.user_email,
            permissions=Permissions.VIEWER_PRESET,
            )
        system_id = mediaserver.api.get_cloud_system_id()
        system_name = f'Change_role_for_user_{time.perf_counter_ns()}'
        cloud_owner.rename_system(system_id, system_name)
        browser = exit_stack.enter_context(browser_stand.browser())
        url = f"https://{cloud_host}/systems/{system_id}"
        browser.open(url)
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        SystemAdministrationPage(browser).wait_for_page_to_be_ready()
        users_dropdown = UsersDropdown(browser)
        users_dropdown.open()
        users_dropdown.get_user_with_email(cloud_viewer.user_email).invoke()
        system_users = SystemUsers(browser)
        user_switch = UserStatusSwitch(browser).get_user_status_switch()
        assert user_switch.is_switched_on()
        user_switch.turn_off()
        system_users.save_button().invoke()
        assert element_is_present(system_users.no_unsaved_changes)
        assert not user_switch.is_switched_on()
        assert "User disabled" in system_users.get_warning_message()
        header = HeaderNav(browser)
        header.account_dropdown().invoke()
        AccountDropdownMenu(browser).log_out_option().invoke()
        _wait_for_correct_location(browser, url=f"https://{cloud_host}/", timeout=10)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_viewer.user_email, cloud_viewer.password)
        assert element_is_present(SystemAdministrationPage(browser).get_no_systems_text)
        header = HeaderNav(browser)
        header.account_dropdown().invoke()
        AccountDropdownMenu(browser).log_out_option().invoke()
        _wait_for_correct_location(browser, url=f"https://{cloud_host}/", timeout=10)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        SystemAdministrationPage(browser).wait_for_page_to_be_ready()
        users_dropdown = UsersDropdown(browser)
        users_dropdown.open()
        users_dropdown.get_user_with_email(cloud_viewer.user_email).invoke()
        system_users = SystemUsers(browser)
        user_switch = UserStatusSwitch(browser).get_user_status_switch()
        assert not user_switch.is_switched_on()
        user_switch.turn_on()
        system_users.save_button().invoke()
        assert element_is_present(system_users.no_unsaved_changes)
        assert user_switch.is_switched_on()
        assert not element_is_present(system_users.get_warning_message)
        header = HeaderNav(browser)
        header.account_dropdown().invoke()
        AccountDropdownMenu(browser).log_out_option().invoke()
        _wait_for_correct_location(browser, url=f"https://{cloud_host}/", timeout=10)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_viewer.user_email, cloud_viewer.password)
        assert not element_is_present(SystemAdministrationPage(browser).get_no_systems_text)
        SystemAdministrationPage(browser).wait_for_page_to_be_ready()


def _wait_for_correct_location(browser: Browser, url: str, timeout: float):
    started_at = time.monotonic()
    while True:
        current_url = browser.get_current_url()
        if current_url == url:
            return
        if time.monotonic() - started_at > timeout:
            raise RuntimeError(
                f"Wrong location. Expected {url}, got {current_url}")
        time.sleep(0.5)


if __name__ == '__main__':
    exit(test_owner_can_disable_enable_user().main())
