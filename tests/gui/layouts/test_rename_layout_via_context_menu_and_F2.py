# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_rename_layout_via_context_menu_and_F2(VMSTest):
    """Rename layout via context menu and F2.

    Layout is saved, then renamed via context menu and F2.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/890

    Selection-Tag: 890
    Selection-Tag: layouts
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        server_vm.api.add_layout_with_resource(
            'New Layout 2',
            server_vm.api.get_web_page_by_name('Support').id,
            )
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        ResourceTree(testkit_api, hid).get_layout('New Layout 2').rename_using_context_menu('Renamed')
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_layout('Renamed')
        assert not rtree.has_layout('New Layout 2')

        rtree.get_layout('Renamed').rename_using_hotkey('Renamed twice')
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_layout('Renamed twice')
        assert not rtree.has_layout('Renamed')


if __name__ == '__main__':
    exit(test_rename_layout_via_context_menu_and_F2().main())
