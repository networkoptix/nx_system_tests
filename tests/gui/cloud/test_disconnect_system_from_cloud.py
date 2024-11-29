# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api.cloud import get_cms_settings
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.cloud_panel import CloudPanel
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from mediaserver_api import MediaserverApiHttpError
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from vm.networks import setup_flat_network


class test_disconnect_system_from_cloud(VMSTest, CloudTest):
    """Disconnect system from Cloud being connected as Cloud owner.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6764
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30444
    Unstable because of https://networkoptix.atlassian.net/browse/VMS-52639

    Selection-Tag: unstable
    Selection-Tag: 6764
    Selection-Tag: 30444
    Selection-Tag: cloud
    Selection-Tag: cloud_portal
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_user = exit_stack.enter_context(cloud_account_factory.temp_account())
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [_, server_vm_cloud, client_installation] = exit_stack.enter_context(
            machine_pool.setup_local_server_cloud_server_client(
                args.cloud_host,
                cloud_user,
                ),
            )

        services_hosts = cloud_user.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [
                *machine_pool.get_vm_objects().values(),
                browser_stand.vm(),
                ],
            IPv4Network('10.254.10.0/28'),
            )
        new_system_name = f'Tile_test_system_{int(time.perf_counter_ns())}'
        _rename_system_when_server_ready(server_vm_cloud, new_system_name)
        # Test Desktop Client side.
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        cloud_panel = CloudPanel(testkit_api, hid)
        cloud_name = get_cms_settings(cloud_host).get_cloud_name()
        cloud_panel.login(cloud_user.user_email, cloud_user.password, cloud_name)
        cloud_panel.wait_for_logged_in()
        cloud_panel_email = cloud_panel.get_email()
        assert cloud_panel_email == cloud_user.user_email, (
            f'Expect email in Cloud Panel: {cloud_user.user_email}, '
            f'Actual: {cloud_panel_email}'
            )
        WelcomeScreen(testkit_api, hid).get_tile_by_system_name(new_system_name).open()
        ResourceTree(testkit_api, hid).wait_for_current_user()
        main_menu = MainMenu(testkit_api, hid)
        system_administration_dialog = main_menu.activate_system_administration()
        system_administration_dialog.open_tab('Nx Cloud')
        disconnect_from_cloud = system_administration_dialog.cloud_tab.open_cloud_disconnection_window()
        disconnect_from_cloud.disconnect_as_cloud_owner()
        # Test Cloud Portal side.
        browser = exit_stack.enter_context(browser_stand.browser())
        link = f"https://{cloud_host}/systems/"
        browser.open(link)
        LoginComponent(browser).login(cloud_user.user_email, cloud_user.password)
        system_administration_page = SystemAdministrationPage(browser)
        assert element_is_present(system_administration_page.get_no_systems_text)


def _rename_system_when_server_ready(mediaserver: Mediaserver, new_system_name: str):
    """Sometimes API sends 'notFound' after system is just connected to Cloud. Rename when ready."""
    started_at = time.monotonic()
    timeout = 5
    while True:
        try:
            mediaserver.api.rename_site(new_system_name)
        except MediaserverApiHttpError as e:
            error_message = "Unable to update the System name on Cloud: notFound"
            if error_message not in str(e):
                raise
            if time.monotonic() - started_at > timeout:
                raise RuntimeError(f"Timed out in {timeout}: {e}")
            _logger.info(f"Trying to rename system after error: {error_message}")
            time.sleep(0.5)
        else:
            return


_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    exit(test_disconnect_system_from_cloud().main())
