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


class test_rename_showreel_to_existing_or_empty_name(VMSTest):
    """Rename showreel to existing or empty name.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/16200

    Selection-Tag: 16200
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
        main_menu.activate_new_showreel()
        ResourceTree(testkit_api, hid).wait_for_showreels_count(2)
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_showreel('Showreel')
        assert rtree.has_showreel('Showreel 2')

        rtree.get_showreel('Showreel 2').rename_using_hotkey('Showreel')
        message_dialog = MessageBox(testkit_api, hid)
        assert message_dialog.wait_until_appears(20).get_title() == 'Overwrite existing showreel?'
        message_dialog.close_by_button('Cancel')
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_showreel('Showreel')
        assert rtree.has_showreel('Showreel 2')

        rtree.get_showreel('Showreel 2').rename_using_hotkey('Showreel')
        message_dialog = MessageBox(testkit_api, hid)
        assert message_dialog.wait_until_appears(20).get_title() == 'Overwrite existing showreel?'
        message_dialog.close_by_button('Overwrite')
        assert ResourceTree(testkit_api, hid).has_showreel('Showreel')

        ResourceTree(testkit_api, hid).get_showreel('Showreel').rename_using_hotkey('')
        assert ResourceTree(testkit_api, hid).has_showreel('Showreel')


if __name__ == '__main__':
    exit(test_rename_showreel_to_existing_or_empty_name().main())
