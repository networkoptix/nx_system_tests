# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_open_several_layouts_context_menu(VMSTest):
    """Open several layouts from context menu.

    Open 3 layouts in resource tree from context menu, check these layouts are open.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1173

    Selection-Tag: 1173
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
        layout_tab_bar = LayoutTabBar(testkit_api, hid)
        layout_tab_bar.save_current_as('Layout1')
        layout_tab_bar.save_current_as('Layout2')
        layout_tab_bar.save_current_as('Layout3')
        ResourceTree(testkit_api, hid).select_layouts(['Layout1', 'Layout2', 'Layout3']).open_in_new_tab()
        assert layout_tab_bar.layout('Layout1')
        assert layout_tab_bar.layout('Layout2')
        assert layout_tab_bar.layout('Layout3')


if __name__ == '__main__':
    exit(test_open_several_layouts_context_menu().main())
