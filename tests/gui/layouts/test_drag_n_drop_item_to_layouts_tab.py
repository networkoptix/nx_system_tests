# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.main_window import MainWindow
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import WebPageSceneItem
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_drag_n_drop_item_to_layouts_tab(VMSTest):
    """layout is created by drag n drop to tab navigator.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1169

    Selection-Tag: 1169
    Selection-Tag: layouts
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
        ResourceTree(testkit_api, hid).get_webpage('Support').drag_n_drop_at(
            MainWindow(testkit_api, hid).bounds().top_left().down(10).right(10),
            )
        scene_item = WebPageSceneItem(testkit_api, hid, 'Support')
        scene_item.wait_for_accessible()
        tab_bar = LayoutTabBar(testkit_api, hid)
        tab_bar.save('New Layout 2*')
        tab_bar.wait_for_open('New Layout 2')
        assert ResourceTree(testkit_api, hid).has_layout('New Layout 2')


if __name__ == '__main__':
    exit(test_drag_n_drop_item_to_layouts_tab().main())
