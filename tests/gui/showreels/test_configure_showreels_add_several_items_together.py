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


class test_configure_showreels_add_several_items_together(VMSTest):
    """Add several items to showreel together.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/16191

    Selection-Tag: 16191
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
        MainMenu(testkit_api, hid).activate_new_showreel()
        ResourceTree(testkit_api, hid).wait_for_showreels_count(1)
        tab_bar = LayoutTabBar(testkit_api, hid)
        tab_bar.create('Test Layout')
        tab_bar.create('Test Layout1')
        tab_bar.create('Test Layout2')
        rtree = ResourceTree(testkit_api, hid)
        showreel_1 = rtree.get_showreel('Showreel').open()
        rtree.get_layout('Test Layout').drag_n_drop_at(showreel_1.get_first_placeholder_coords())
        rtree.get_layout('Test Layout1').drag_n_drop_at(showreel_1.get_first_placeholder_coords())
        rtree.get_layout('Test Layout2').drag_n_drop_at(showreel_1.get_first_placeholder_coords())
        assert showreel_1.get_item_names() == ['Test Layout', 'Test Layout1', 'Test Layout2']

        rtree.get_layout('Test Layout').drag_n_drop_at(showreel_1.get_first_placeholder_coords())
        rtree.get_layout('Test Layout1').drag_n_drop_at(showreel_1.get_first_placeholder_coords())
        rtree.get_layout('Test Layout2').drag_n_drop_at(showreel_1.get_first_placeholder_coords())
        assert showreel_1.get_item_names() == ['Test Layout', 'Test Layout1', 'Test Layout2', 'Test Layout', 'Test Layout1', 'Test Layout2']

        tab_bar.close('Showreel')
        showreel_2 = rtree.get_showreel('Showreel').open()
        assert showreel_2.get_item_names() == ['Test Layout', 'Test Layout1', 'Test Layout2', 'Test Layout', 'Test Layout1', 'Test Layout2']


if __name__ == '__main__':
    exit(test_configure_showreels_add_several_items_together().main())
