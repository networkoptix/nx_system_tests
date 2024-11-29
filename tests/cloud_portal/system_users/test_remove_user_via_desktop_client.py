# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ElementNotFound
from cloud_api.cloud import get_cms_settings
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.cloud_panel import CloudPanel
from gui.desktop_ui.dialogs.system_administration import SystemAdministrationDialog
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import Groups
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._not_existing_page import FailedToAccessSystemPage
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._system_left_menu import UsersDropdown
from tests.web_admin._interface_wait import element_is_present
from vm.networks import setup_flat_network


class test_remove_user_via_desktop_client(VMSTest, CloudTest):
    """Test Cloud owner can remove Cloud user in Desktop Client, removed user is not seen in Cloud Portal.

    Selection-Tag: 30727
    Selection-Tag: cloud_portal
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30727
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = cloud_account_factory.create_account()
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_owner.set_user_customization(customization_name)
        services_hosts = cloud_owner.get_services_hosts()
        [mediaserver, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        client_installation.set_ini('desktop_client.ini', {'cloudHost': cloud_host})
        mediaserver.os_access.cache_dns_in_etc_hosts(
            [cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.stop()
        mediaserver.set_cloud_host(cloud_host)
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [
                machine_pool.get_vm_objects()['VM'],
                machine_pool.get_vm_objects()['CLIENT'],
                browser_stand.vm(),
                ],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver.start()
        system_name = mediaserver.api.get_system_name()
        bind_info = cloud_owner.bind_system(system_name=system_name)
        mediaserver.api.connect_system_to_cloud(
            bind_info.auth_key,
            bind_info.system_id,
            cloud_owner.user_email,
            )
        new_system_name = f'Tile_test_system_{int(time.perf_counter_ns())}'
        mediaserver.api.rename_site(new_system_name)
        second_cloud_user = cloud_account_factory.create_account()
        second_cloud_user.set_user_customization(customization_name)
        mediaserver.api.add_cloud_user(
            name=second_cloud_user.user_email,
            email=second_cloud_user.user_email,
            group_id=Groups.POWER_USERS,
            )
        # Test Desktop Client side.
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(mediaserver),
            machine_pool.get_testkit_port(),
            client_installation,
            mediaserver,
            )
        hid = HID(testkit_api)
        main_menu = MainMenu(testkit_api, hid)
        dialog = main_menu.activate_user_management()
        user_settings_dialog = dialog.open_user_settings(second_cloud_user.user_email)
        user_settings_dialog.select_general_tab().start_removing()
        warning_dialog = MessageBox(testkit_api, hid).wait_until_appears()
        warning_dialog.close_by_button('Delete')
        assert not dialog.has_user(second_cloud_user.user_email)
        SystemAdministrationDialog(testkit_api, hid).save_and_close()
        main_menu.disconnect_from_server()
        cloud_panel = CloudPanel(testkit_api, hid)
        cloud_name = get_cms_settings(cloud_host).get_cloud_name()
        cloud_panel.login(second_cloud_user.user_email, second_cloud_user.password, cloud_name)
        cloud_panel.wait_for_logged_in()
        tile = WelcomeScreen(testkit_api, hid).get_tile_by_system_name(new_system_name)
        assert not tile.has_cloud_icon()
        # Test Cloud Portal side.
        browser = exit_stack.enter_context(browser_stand.browser())
        link = f"https://{cloud_host}/systems/{mediaserver.api.get_cloud_system_id()}"
        browser.open(link)
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        # It takes time for the system status to be updated on Cloud Portal.
        system_administration_page = SystemAdministrationPage(browser)
        system_administration_page.wait_for_system_name_field(timeout=90)
        users_dropdown = UsersDropdown(browser)
        users_dropdown.open()
        assert not users_dropdown.has_user_with_email(second_cloud_user.user_email)
        header = HeaderNav(browser)
        header.account_dropdown().invoke()
        AccountDropdownMenu(browser).log_out_option().invoke()
        _wait_for_url(browser, url=f"https://{cloud_host}/", timeout=10)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(second_cloud_user.user_email, second_cloud_user.password)
        assert element_is_present(header.account_dropdown)
        browser.open(link)
        try:
            FailedToAccessSystemPage(browser).wait_for_failed_to_access_text()
        except ElementNotFound:
            raise AssertionError(
                "Redirects to home page but does not load disconnected system."
                "See: https://networkoptix.atlassian.net/browse/CLOUD-14034")


def _wait_for_url(browser: Browser, url: str, timeout: float):
    started_at = time.monotonic()
    while True:
        current_url = browser.get_current_url()
        if current_url == url:
            return
        if time.monotonic() - started_at > timeout:
            raise RuntimeError(
                f"Wrong location. Expected {url}, got {current_url} within {timeout} seconds")
        time.sleep(0.5)


if __name__ == '__main__':
    exit(test_remove_user_via_desktop_client().main())
