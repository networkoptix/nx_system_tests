# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_remove_showreels(VMSTest):
    """Remove showreel.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/16185

    Selection-Tag: 16185
    Selection-Tag: showreels
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
        main_menu = MainMenu(testkit_api, hid)
        main_menu.activate_new_showreel()
        ResourceTree(testkit_api, hid).wait_for_showreels_count(1)
        ResourceTree(testkit_api, hid).get_showreel('Showreel').start_removing()
        MessageBox(testkit_api, hid).close_by_button('Cancel')
        assert ResourceTree(testkit_api, hid).count_showreels() == 1

        ResourceTree(testkit_api, hid).get_showreel('Showreel').remove()
        ResourceTree(testkit_api, hid).wait_for_showreels_count(0)

        main_menu.activate_new_showreel()
        main_menu.activate_new_showreel()
        main_menu.activate_new_showreel()
        ResourceTree(testkit_api, hid).wait_for_showreels_count(3)
        # TODO revisit when VMS-11083 is fixed.
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.count_showreels() == 3
        rtree.select_all_showreels().remove()


if __name__ == '__main__':
    exit(test_remove_showreels().main())
