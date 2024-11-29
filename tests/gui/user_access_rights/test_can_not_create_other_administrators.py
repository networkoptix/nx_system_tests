# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_can_not_create_other_administrators(VMSTest):
    """Can not create other Administrators.

    # https://networkoptix.testrail.net/index.php?/cases/view/115044

    Selection-Tag: users_and_group_management
    Selection-Tag: 115044
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
        main_menu = MainMenu(testkit_api, hid)
        dialog = main_menu.activate_user_management()
        new_user_dialog = dialog.open_new_user_dialog()

        built_in_groups = new_user_dialog.groups_tab().get_group_names()
        admin_group_name = 'Administrators'
        assert admin_group_name not in built_in_groups, f'{admin_group_name} in {built_in_groups}'
        new_user_dialog.close_by_cancel_button()

        group_edit_dialog = dialog.open_group_settings(admin_group_name)
        selectable_group_names = group_edit_dialog.get_members_tab().get_selectable_group_members()
        assert len(selectable_group_names) == 0, f'Groups found: {selectable_group_names}'


if __name__ == '__main__':
    exit(test_can_not_create_other_administrators().main())
