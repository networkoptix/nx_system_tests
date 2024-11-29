# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_add_members_to_custom_group(VMSTest):
    """Add members to custom group.

    # https://networkoptix.testrail.net/index.php?/cases/view/115084

    Selection-Tag: users_and_group_management
    Selection-Tag: 115084
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())  # Background and scenario
        # Background
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        user_1 = server_vm.api.add_local_user(
            name='User_1',
            password='ArbitraryPassword',
            )
        user_2 = server_vm.api.add_local_user(
            name='User_2',
            password='ArbitraryPassword',
            )
        user_3 = server_vm.api.add_local_user(
            name='User_3',
            password='ArbitraryPassword',
            )
        group_name = 'Test Group'
        server_vm.api.add_user_group(group_name, ['none'])
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        # VMSTest
        user_management = MainMenu(testkit_api, hid).activate_user_management()
        assert user_management.get_groups(user_1.name) == ''
        assert user_management.get_groups(user_2.name) == ''
        assert user_management.get_groups(user_3.name) == ''

        user_1_settings = user_management.open_user_settings(user_1.name)
        user_1_settings.select_general_tab().set_group(group_name)
        user_1_settings.save_and_close()
        assert user_management.get_groups(user_1.name) == group_name

        group_settings = user_management.open_group_settings(group_name)
        members_tab = group_settings.get_members_tab()
        members_tab.add_user(user_2.name)
        members_tab.add_user(user_3.name)
        group_settings.save_and_close()
        assert user_management.get_groups(user_2.name) == group_name
        assert user_management.get_groups(user_3.name) == group_name


if __name__ == '__main__':
    exit(test_add_members_to_custom_group().main())
