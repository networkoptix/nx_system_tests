# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_can_edit_custom_group(VMSTest):
    """Can edit custom group.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/115004

    Selection-Tag: users_and_group_management
    Selection-Tag: 115004
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())  # Background and scenario
        # Background
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        admin_name = 'root'
        server_vm.api.add_local_admin(admin_name, 'WellKnownPassword2')
        group_name = 'Test'
        server_vm.api.add_user_group(group_name, ['none'])
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        # VMSTest
        dialog = MainMenu(testkit_api, hid).activate_user_management()
        group_settings_dialog = dialog.open_group_settings(group_name)

        general_tab = group_settings_dialog.get_general_tab()
        updated_group_name = f'{group_name}(Updated)'
        general_tab.set_new_name(updated_group_name)
        updated_group_description = 'Test Description(Updated)'
        general_tab.set_new_description(updated_group_description)
        group_settings_dialog.get_members_tab().add_user(admin_name)
        group_settings_dialog.save_and_close()

        group_data = dialog.get_group_data_by_name(updated_group_name)
        assert group_data['description'] == updated_group_description
        power_user_data = dialog.get_user_data_by_name(admin_name)
        assert power_user_data['groups'] == f'Power Users, {updated_group_name}'


if __name__ == '__main__':
    exit(test_can_edit_custom_group().main())
