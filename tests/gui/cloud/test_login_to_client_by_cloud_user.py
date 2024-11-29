# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

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


class test_login_to_client_by_cloud_user(VMSTest, CloudTest):
    """Login to Desktop Client by Cloud User.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30825
    Unstable because of https://networkoptix.atlassian.net/browse/VMS-52639

    Selection-Tag: unstable
    Selection-Tag: 30825
    Selection-Tag: cloud
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_user = exit_stack.enter_context(cloud_account_factory.temp_account())
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm_local, server_vm_cloud, client_installation] = exit_stack.enter_context(
            machine_pool.setup_local_server_cloud_server_client(
                cloud_host,
                cloud_user,
                ),
            )

        first_system_name = f'Tile_first_test_system_{int(time.perf_counter_ns())}'
        _rename_system_when_server_ready(server_vm_local, first_system_name)

        second_system_name = f'Tile_second_test_system_{int(time.perf_counter_ns())}'
        _rename_system_when_server_ready(server_vm_cloud, second_system_name)

        bind_info = cloud_user.bind_system(server_vm_local.api.get_system_name())
        server_vm_local.api.connect_system_to_cloud(
            bind_info.auth_key, bind_info.system_id, cloud_user.user_email)

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

        welcome_screen = WelcomeScreen(testkit_api, hid)
        welcome_screen.wait_for_tile_appear(first_system_name, wait_time=20)
        first_tile = welcome_screen.get_tile_by_system_name(first_system_name)
        assert first_tile.has_cloud_icon()
        second_system_tile = welcome_screen.get_tile_by_system_name(second_system_name)
        assert second_system_tile.has_cloud_icon()


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
    exit(test_login_to_client_by_cloud_user().main())
