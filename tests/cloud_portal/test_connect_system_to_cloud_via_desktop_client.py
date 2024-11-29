# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
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
from installation import Mediaserver
from mediaserver_api import MediaserverApiHttpError
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from vm.networks import setup_flat_network


class test_connect_system_to_cloud_via_desktop_client(VMSTest, CloudTest):
    """Connect system to Cloud and check on Cloud Portal.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30443

    Selection-Tag: 30443
    Selection-Tag: cloud
    Selection-Tag: cloud_portal
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = exit_stack.enter_context(cloud_account_factory.temp_account())
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
        new_system_name = f'Tile_test_system_{int(time.perf_counter_ns())}'
        _rename_system_when_server_ready(mediaserver, new_system_name)
        # Test Desktop Client side.
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(mediaserver),
            machine_pool.get_testkit_port(),
            client_installation,
            mediaserver,
            )
        hid = HID(testkit_api)
        main_menu = MainMenu(testkit_api, hid)
        system_administration_dialog = main_menu.activate_system_administration()
        system_administration_dialog.open_tab('Nx Cloud')
        cloud_tab = system_administration_dialog.cloud_tab
        local_system_password = mediaserver.api.get_credentials().password
        cloud_name = get_cms_settings(cloud_host).get_cloud_name()
        cloud_tab.connect_system_to_cloud(
            cloud_owner.user_email,
            cloud_owner.password,
            local_system_password,
            cloud_name,
            )
        assert cloud_tab.get_disconnect_from_cloud_button().is_accessible_timeout(timeout=5)
        assert cloud_tab.is_system_connected()
        assert cloud_tab.get_connected_account() == cloud_owner.user_email
        # Test Cloud Portal side.
        browser = exit_stack.enter_context(browser_stand.browser())
        system_id = mediaserver.api.get_cloud_system_id()
        cms_data = get_cms_settings(cloud_host)
        if cms_data.flag_is_enabled('channelPartners'):
            # With the new Channel Partners interface, the only system doesn't open automatically.
            browser.open(f'https://{cloud_host}/systems/{system_id}')
        else:
            browser.open(f'https://{cloud_host}/systems/')
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        SystemAdministrationPage(browser).wait_for_system_name_field(timeout=90)


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
    exit(test_connect_system_to_cloud_via_desktop_client().main())
