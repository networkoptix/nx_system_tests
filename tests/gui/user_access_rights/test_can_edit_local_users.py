# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_can_edit_local_users(VMSTest):
    """Can edit local users.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/114999

    Selection-Tag: users_and_group_management
    Selection-Tag: 114999
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
        viewer_login = 'Viewer'
        viewer_password = 'ArbitraryPassword'
        server_vm.api.add_local_viewer(
            username=viewer_login,
            password=viewer_password,
            )
        # VMSTest
        main_menu = MainMenu(testkit_api, hid)
        dialog = main_menu.activate_user_management()
        user_settings_dialog = dialog.open_user_settings(viewer_login)

        updated_viewer_login = f'{viewer_login}(Updated)'
        general_tab = user_settings_dialog.select_general_tab()
        general_tab.set_login(updated_viewer_login)
        full_name = 'Full Name'
        general_tab.set_full_name(full_name)
        email = 'example@mail.com'
        general_tab.set_email(email)
        power_users_group_name = 'Power Users'
        user_settings_dialog.select_groups_tab().toggle_group(power_users_group_name)
        user_settings_dialog.save_and_close()

        user_data = dialog.get_user_data_by_name(updated_viewer_login)
        assert user_data['name'] == full_name
        assert user_data['email'] == email
        assert user_data['groups'] == f'{power_users_group_name}, Viewers'

        main_menu.disconnect_from_server()
        address, port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        main_menu.activate_connect_to_server().connect(
            address=address,
            user=updated_viewer_login,
            password=viewer_password,
            port=port,
            )
        ResourceTree(testkit_api, hid).wait_for_current_user()


if __name__ == '__main__':
    exit(test_can_edit_local_users().main())
