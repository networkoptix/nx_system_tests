# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from doubles.http_server.http_server import create_test_http_server
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import WebPageSceneItem
from gui.desktop_ui.showreels import Showreel
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_showreels_autorun_with_not_saved_password(VMSTest):
    """Showreel autorun with not saved password.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/16202

    Selection-Tag: 16202
    Selection-Tag: showreels
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        test_http_server = create_test_http_server('dropdown_page')
        exit_stack.enter_context(test_http_server)
        link = f'http://{client_installation.os_access.source_address()}:{test_http_server.server_port}'
        server_vm.api.add_web_page('Test', link)
        testkit_api_1 = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid_1 = HID(testkit_api_1)
        MainMenu(testkit_api_1, hid_1).activate_new_showreel()
        ResourceTree(testkit_api_1, hid_1).wait_for_showreels_count(1)
        showreel = Showreel(testkit_api_1, hid_1)
        ResourceTree(testkit_api_1, hid_1).get_webpage('Test').drag_n_drop_at(showreel.get_first_placeholder_coords())
        showreel.start()
        time.sleep(5)
        # This differs from "close all clients" step and simulates unexpected exit.
        client_installation.kill_client_process()
        testkit_api_2 = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid_2 = HID(testkit_api_2)

        assert WebPageSceneItem(testkit_api_2, hid_2, 'Test').is_expanded()


if __name__ == '__main__':
    exit(test_showreels_autorun_with_not_saved_password().main())
