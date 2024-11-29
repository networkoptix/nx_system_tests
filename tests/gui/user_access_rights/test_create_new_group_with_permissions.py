# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_create_new_group_with_permissions(VMSTest):
    """Can edit local users.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/115051

    Selection-Tag: users_and_group_management
    Selection-Tag: 115051
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())  # Background and scenario
        # Background
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        # VMSTest
        dialog = MainMenu(testkit_api, hid).activate_user_management()
        new_group_dialog = dialog.open_new_group_dialog()
        group_name = 'Test'
        group_description = 'Description'
        new_group_dialog.set_name(group_name)
        new_group_dialog.set_description(group_description)
        resources_tab = new_group_dialog.get_resources_tab()
        cell = resources_tab.get_resource('Cameras & Devices').permission('View Live')
        hid.mouse_left_click(cell.bounds().center())
        new_group_dialog.click_add_group_button()
        group_data = dialog.get_group_data_by_name(group_name)
        assert group_data['description'] == group_description

        group_settings = dialog.open_group_settings(group_name)
        resources_tab = group_settings.get_resources_tab()
        cell = resources_tab.get_resource('Cameras & Devices').permission('View Live')
        hid.mouse_left_click(cell.bounds().center())
        group_settings.save_and_close()


if __name__ == '__main__':
    exit(test_create_new_group_with_permissions().main())
