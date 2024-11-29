# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_save_layout_as_for_new_by_context_menu(VMSTest):
    """Save Layout As for a new layout by context menu.

    "Save Layout As..." for a new layout by context menu

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/814

    Selection-Tag: 814
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
        Scene(testkit_api, hid).save_current_as('Test name')
        assert LayoutTabBar(testkit_api, hid).is_open('Test name')
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_layout('Test name')
        assert not rtree.has_layout('New Layout 1')


if __name__ == '__main__':
    exit(test_save_layout_as_for_new_by_context_menu().main())
