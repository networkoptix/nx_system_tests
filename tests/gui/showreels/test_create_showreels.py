# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_create_showreels(VMSTest):
    """Create showreel in different ways.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/16195

    Selection-Tag: 16195
    Selection-Tag: showreels
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
        # From Main menu.
        MainMenu(testkit_api, hid).activate_new_showreel()
        ResourceTree(testkit_api, hid).wait_for_showreels_count(1)
        rtree = ResourceTree(testkit_api, hid)
        showreel_1 = rtree.get_showreel('Showreel').open()
        assert showreel_1.count_items() == 0

        # From resources tree.
        showreel_2 = rtree.get_showreels_node().create_new_showreel()
        assert showreel_2.get_showreel_name() == 'Showreel 2'
        assert showreel_2.count_items() == 0

        # From layout.
        layout_tab_bar = LayoutTabBar(testkit_api, hid)
        layout_tab_bar.add_new_tab()
        layout_tab_bar.save_current_as('test layout 1')
        showreel_3 = ResourceTree(testkit_api, hid).select_layouts(['test layout 1']).make_showreel()
        assert showreel_3.get_showreel_name() == 'Showreel 3'
        assert showreel_3.has_item('test layout 1')

        # From several layouts.
        layout_tab_bar.add_new_tab()
        layout_tab_bar.save_current_as('test layout 2')
        showreel_4 = ResourceTree(testkit_api, hid).select_layouts(['test layout 1', 'test layout 2']).make_showreel()
        assert showreel_4.get_showreel_name() == 'Showreel 4'
        assert showreel_4.has_item('test layout 1')
        assert showreel_4.has_item('test layout 2')


if __name__ == '__main__':
    exit(test_create_showreels().main())
