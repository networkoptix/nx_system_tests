# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_open_several_layouts(VMSTest):
    """Open several layouts by drag n drop.

    Drag-and-drop two layouts from resource tree to the scene, check these layouts are open.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1175

    Selection-Tag: 1175
    Selection-Tag: layouts
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        tab_bar = LayoutTabBar(testkit_api, hid)
        tab_bar.save_current_as('Layout1')
        tab_bar.save_current_as('Layout2')
        tab_bar.save_current_as('Layout3')
        ResourceTree(testkit_api, hid).select_layouts(['Layout1', 'Layout2']).drag_n_drop_on_scene()
        time.sleep(1)
        assert tab_bar.is_open('Layout1')
        assert tab_bar.is_open('Layout2')
        assert tab_bar.is_open('Layout3')


if __name__ == '__main__':
    exit(test_open_several_layouts().main())
