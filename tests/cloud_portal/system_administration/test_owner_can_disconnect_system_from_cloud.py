# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api.cloud import get_cms_settings
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import DisconnectFromCloudModal
from tests.cloud_portal._system_administration_page import DisconnectedFromCloudToast
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._translation import en_us
from vm.networks import setup_flat_network


class test_owner_can_disconnect_system_from_cloud(VMSTest, CloudTest):
    """Test owner can disconnect system from Cloud.

    Selection-Tag: 41883
    Selection-Tag: 69845
    Selection-Tag: cloud_portal
    Selection-Tag: unstable
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/41883
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/69845
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        distrib_url = args.distrib_url
        machine_pool = GuiTestStand(ClassicInstallerSupplier(distrib_url), get_run_dir())
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = cloud_account_factory.create_account()
        services_hosts = cloud_owner.get_services_hosts()
        [mediaserver, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        client_installation.set_ini('desktop_client.ini', {'cloudHost': cloud_host})
        mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
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
            bind_info.auth_key, bind_info.system_id, cloud_owner.user_email)
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f'https://{cloud_host}')
        header = HeaderNav(browser, en_us)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        header.get_systems_link().invoke()
        system_admin = SystemAdministrationPage(browser)
        system_admin.get_disconnect_from_cloud_button().invoke()
        disconnect_modal = DisconnectFromCloudModal(browser)
        disconnect_modal.get_close_button().invoke()
        assert system_admin.get_merge_with_another_system_button().is_active()
        system_admin.get_disconnect_from_cloud_button().invoke()
        disconnect_modal.get_cancel_button().invoke()
        assert system_admin.get_merge_with_another_system_button().is_active()
        system_admin.get_disconnect_from_cloud_button().invoke()
        disconnect_modal.get_disconnect_system_button().invoke()
        cms_settings = get_cms_settings(cloud_host)
        cloud_name = cms_settings.get_cloud_name()
        disconnected_toast = DisconnectedFromCloudToast(browser, en_us, cloud_name=cloud_name)
        disconnected_toast.wait_until_shown(2)
        disconnected_toast.wait_until_not_shown(10)
        # CLOUD-13021: Redirect doesn't happen in ChromeDriver-controlled browser.
        assert browser.get_current_url() == f'https://{cloud_host}/systems'
        assert len(cloud_owner.get_systems()) == 0
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(mediaserver),
            machine_pool.get_testkit_port(),
            client_installation,
            mediaserver,
            )
        hid = HID(testkit_api)
        system_administration_dialog = MainMenu(testkit_api, hid).activate_system_administration()
        system_administration_dialog.open_tab('Nx Cloud')
        system_administration_dialog.cloud_tab.wait_for_disconnected()


if __name__ == '__main__':
    exit(test_owner_can_disconnect_system_from_cloud().main())
