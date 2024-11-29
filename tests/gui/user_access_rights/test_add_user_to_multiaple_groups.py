# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_add_user_to_multiaple_groups(VMSTest):
    """Add user to multiple groups.

    # https://networkoptix.testrail.net/index.php?/cases/view/115082

    Selection-Tag: users_and_group_management
    Selection-Tag: 115082
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())  # Background and scenario
        # Background
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        user = server_vm.api.add_local_user(
            name='User',
            password='ArbitraryPassword',
            )
        group_name_1, group_name_2, group_name_3 = 'Group_1', 'Group_2', 'Group_3'
        server_vm.api.add_user_group(group_name_1, ['none'])
        server_vm.api.add_user_group(group_name_2, ['none'])
        server_vm.api.add_user_group(group_name_3, ['none'])
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        # VMSTest
        user_management = MainMenu(testkit_api, hid).activate_user_management()
        user_settings = user_management.open_user_settings(user.name)
        groups_tab = user_settings.select_groups_tab()
        groups_tab.toggle_group(group_name_1)
        groups_tab.toggle_group(group_name_2)
        groups_tab.toggle_group(group_name_3)
        general_tab = user_settings.select_general_tab()
        selected_groups = general_tab.get_selected_groups_names()
        assert selected_groups == [group_name_1, group_name_2, group_name_3]
        user_settings.save_and_close()
        user_groups = user_management.get_groups(user.name)
        assert f'{group_name_1}, {group_name_2}, {group_name_3}' == user_groups


if __name__ == '__main__':
    exit(test_add_user_to_multiaple_groups().main())
