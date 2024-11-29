# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from ipaddress import IPv4Network

from cloud_api.cloud import get_cms_settings
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.cloud_panel import CloudPanel
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from mediaserver_api import MediaserverApiHttpError
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from vm.networks import setup_flat_network


class test_check_system_state_in_desktop_client(VMSTest, CloudTest):
    """Test Cloud owner can see changes of Cloud system online status in Desktop Client.

    Selection-Tag: 30827
    Selection-Tag: cloud_portal
    Selection-Tag: unstable

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30827
    Unstable because of https://networkoptix.atlassian.net/browse/VMS-52639
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
        setup_flat_network(
            [
                machine_pool.get_vm_objects()['VM'],
                machine_pool.get_vm_objects()['CLIENT'],
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
        new_system_name = f'Tile_test_system_{int(time.perf_counter_ns())}'
        _rename_system_when_server_ready(mediaserver, new_system_name)
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        cloud_panel = CloudPanel(testkit_api, hid)
        cloud_name = get_cms_settings(cloud_host).get_cloud_name()
        cloud_panel.login(cloud_owner.user_email, cloud_owner.password, cloud_name)
        cloud_panel.wait_for_logged_in()
        # Sometimes "Your session has expired" dialog appears after login.
        # See: https://networkoptix.atlassian.net/browse/VMS-52639
        welcome_screen = WelcomeScreen(testkit_api, hid)
        tile = welcome_screen.get_tile_by_system_name(new_system_name)
        assert tile.has_cloud_icon()
        mediaserver.stop()
        tile.wait_until_unreachable(timeout=20)
        mediaserver.start()
        tile.wait_until_online(timeout=20)


def _rename_system_when_server_ready(mediaserver: Mediaserver, new_system_name: str):
    """Sometimes API sends 'notFound' after system is just connected to Cloud. Rename when ready."""
    started_at = time.monotonic()
    timeout = 30
    while True:
        try:
            mediaserver.api.rename_site(new_system_name)
        except MediaserverApiHttpError as e:
            error_message = "Unable to update the System name on Cloud: notFound"
            if error_message not in str(e):
                raise
            if time.monotonic() - started_at > timeout:
                raise RuntimeError(f"Timed out in {timeout} seconds: {e}")
            _logger.info(f"Trying to rename system after error: {error_message}")
            time.sleep(1)
        else:
            return


_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    exit(test_check_system_state_in_desktop_client().main())
