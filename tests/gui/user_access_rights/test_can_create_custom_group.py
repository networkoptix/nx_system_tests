# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_can_create_custom_group(VMSTest):
    """Can create custom group.

    # https://networkoptix.testrail.net/index.php?/cases/view/115003
    # https://networkoptix.testrail.net/index.php?/cases/view/115054
    # https://networkoptix.testrail.net/index.php?/cases/view/115052
    # https://networkoptix.testrail.net/index.php?/cases/view/115050

    Selection-Tag: users_and_group_management
    Selection-Tag: 115003
    Selection-Tag: 115054
    Selection-Tag: 115052
    Selection-Tag: 115050
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
        initial_group_count = dialog.get_groups_count()
        dialog.open_new_group_dialog().close_by_cancel()
        current_groups_count = dialog.get_groups_count()
        assert initial_group_count == current_groups_count, f'Actual: {current_groups_count}, Expected: {initial_group_count}'
        new_group_dialog_1 = dialog.open_new_group_dialog()
        new_group_dialog_1.clear_name_field()
        new_group_dialog_1.click_add_group_button()
        expected_warning_message_1 = 'Group name cannot be empty'
        warning_message_1 = new_group_dialog_1.get_warning_text()
        assert warning_message_1 == expected_warning_message_1, f'Actual: {warning_message_1}, Expected: {expected_warning_message_1}'
        new_group_dialog_1.close_by_cancel()
        current_groups_count = dialog.get_groups_count()
        assert initial_group_count == current_groups_count, f'Actual: {current_groups_count}, Expected: {initial_group_count}'

        new_group_dialog_2 = dialog.open_new_group_dialog()
        new_group_dialog_2.set_name('Administrators')
        new_group_dialog_2.click_add_group_button()
        expected_warning_message_2 = 'Group with the same name already exists'
        warning_message = new_group_dialog_2.get_warning_text()
        assert warning_message == expected_warning_message_2, f'Actual: {warning_message}, Expected: {expected_warning_message_2}'

        new_group_dialog_2.set_name('Power Users')
        new_group_dialog_2.click_add_group_button()
        warning_message = new_group_dialog_2.get_warning_text()
        assert warning_message == expected_warning_message_2, f'Actual: {warning_message}, Expected: {expected_warning_message_2}'

        new_group_dialog_2.set_name('Viewers')
        new_group_dialog_2.click_add_group_button()
        warning_message = new_group_dialog_2.get_warning_text()
        assert warning_message == expected_warning_message_2, f'Actual: {warning_message}, Expected: {expected_warning_message_2}'

        new_group_dialog_2.set_name('Advanced viewers')
        new_group_dialog_2.click_add_group_button()
        warning_message = new_group_dialog_2.get_warning_text()
        assert warning_message == expected_warning_message_2, f'Actual: {warning_message}, Expected: {expected_warning_message_2}'

        new_group_dialog_2.set_name('Live Viewers')
        new_group_dialog_2.click_add_group_button()
        warning_message = new_group_dialog_2.get_warning_text()
        assert warning_message == expected_warning_message_2, f'Actual: {warning_message}, Expected: {expected_warning_message_2}'

        group_name = 'Test'
        group_description = 'Description'
        new_group_dialog_2.create_new_group(name=group_name, description=group_description)
        group_data = dialog.get_group_data_by_name(group_name)
        assert group_data['description'] == group_description


if __name__ == '__main__':
    exit(test_can_create_custom_group().main())
