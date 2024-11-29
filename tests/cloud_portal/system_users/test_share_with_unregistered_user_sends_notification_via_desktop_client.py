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
from tests.cloud_portal._confirmations import AccountActivatedConfirmation
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._register_form import RegisterPage
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from vm.networks import setup_flat_network


class test_share_with_unregistered_user_sends_notification_via_desktop_client(VMSTest, CloudTest):
    """Test that sharing the system with unregistered user via Desktop Client triggers notification.

    Selection-Tag: 30447
    Selection-Tag: cloud_portal
    Selection-Tag: xfail
    xfail reason: https://networkoptix.atlassian.net/browse/VMS-52639
    xfail reason: https://networkoptix.atlassian.net/browse/CLOUD-14247
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30447
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
        system_name = mediaserver.api.get_system_name()
        bind_info = cloud_owner.bind_system(system_name=system_name)
        mediaserver.api.connect_system_to_cloud(
            bind_info.auth_key,
            bind_info.system_id,
            cloud_owner.user_email,
            )
        new_system_name = f'Tile_test_system_{time.perf_counter_ns()}'
        mediaserver.api.rename_site(new_system_name)
        unregistered_cloud_user = cloud_account_factory.create_unregistered_account()
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
        # Sometimes "Your session has expired" dialog appears after login.
        # See: https://networkoptix.atlassian.net/browse/VMS-52639
        user_management = MainMenu(testkit_api, hid).activate_user_management()
        full_name = cloud_owner.get_user_info().get_full_name()
        user_management.add_cloud_user(unregistered_cloud_user.user_email, ["Viewers"])
        with IMAPConnection(*cloud_account_factory.get_imap_credentials()) as imap_connection:
            subject = f"{full_name} invites you to {cloud_name}"
            # Wrong subject in the letter when unregistered Cloud user is added via Desktop Client.
            # See: https://networkoptix.atlassian.net/browse/CLOUD-14247
            message_id = imap_connection.get_message_id_by_subject(unregistered_cloud_user.user_email, subject)
            assert imap_connection.has_link_to_cloud_instance_in_message(message_id, cloud_host)
            register_link = imap_connection.get_register_link_from_message(message_id)
        # Test Cloud Portal side.
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(register_link)
        register_page = RegisterPage(browser)
        email_field = register_page.get_locked_email_field()
        assert email_field.get_value() == unregistered_cloud_user.user_email
        assert email_field.is_readonly()
        register_page.register("Mark", "Hamill", unregistered_cloud_user.password)
        account_activated = AccountActivatedConfirmation(browser)
        account_activated.wait_for_account_activated_text()
        account_activated.log_in()
        LoginComponent(browser).login_with_password_only(unregistered_cloud_user.password)
        assert element_is_present(HeaderNav(browser).account_dropdown)
        # It takes time for the system status to be updated on Cloud portal.
        SystemAdministrationPage(browser).wait_for_system_name_field(timeout=90)


if __name__ == '__main__':
    exit(test_share_with_unregistered_user_sends_notification_via_desktop_client().main())
