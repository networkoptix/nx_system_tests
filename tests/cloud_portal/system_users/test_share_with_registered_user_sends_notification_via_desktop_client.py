# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api._imap import IMAPConnection
from cloud_api.cloud import get_cms_settings
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.cloud_panel import CloudPanel
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from vm.networks import setup_flat_network


class test_share_with_registered_user_sends_notification_via_desktop_client(VMSTest, CloudTest):
    """Test that sharing the system with registered user via Desktop Client triggers notification.

    Selection-Tag: 30448
    Selection-Tag: cloud_portal
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30448
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
        [mediaserver, client_installation] = exit_stack.enter_context(
            machine_pool.setup_server_client_for_cloud_tests(
                args.cloud_host,
                services_hosts=services_hosts,
                ),
            )
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [
                machine_pool.get_vm_objects()['VM'],
                machine_pool.get_vm_objects()['CLIENT'],
                browser_stand.vm(),
                ],
            IPv4Network('10.254.10.0/28'),
            )
        api = mediaserver.api
        system_name = api.get_system_name()
        bind_info = cloud_owner.bind_system(system_name=system_name)
        api.connect_system_to_cloud(
            bind_info.auth_key,
            bind_info.system_id,
            cloud_owner.user_email,
            )
        new_system_name = f'Tile_test_system_{time.perf_counter_ns()}'
        api.rename_site(new_system_name)
        registered_user = cloud_account_factory.create_account()
        registered_user.set_user_customization(customization_name)
        # Test Desktop Client side.
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(mediaserver),
            machine_pool.get_testkit_port(),
            client_installation,
            mediaserver,
            )
        hid = HID(testkit_api)
        cloud_panel = CloudPanel(testkit_api, hid)
        cloud_name = get_cms_settings(cloud_host).get_cloud_name()
        cloud_panel.login(cloud_owner.user_email, cloud_owner.password, cloud_name)
        cloud_panel.wait_for_logged_in()
        user_management = MainMenu(testkit_api, hid).activate_user_management()
        user_management.add_cloud_user(registered_user.user_email, ["Viewers"])
        with IMAPConnection(*cloud_account_factory.get_imap_credentials()) as imap_connection:
            subject = f"Video system {api.get_system_name()} was shared with you"
            message_id = imap_connection.get_message_id_by_subject(registered_user.user_email, subject)
            assert imap_connection.has_link_to_cloud_instance_in_message(message_id, cloud_host)
            link_to_system_page = imap_connection.get_link_to_cloud_system(message_id)
        # Test Cloud Portal side.
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(link_to_system_page)
        LoginComponent(browser).login(registered_user.user_email, registered_user.password)
        assert element_is_present(HeaderNav(browser).account_dropdown)


if __name__ == '__main__':
    exit(test_share_with_registered_user_sends_notification_via_desktop_client().main())
