# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.messages import MessageBox
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_can_delete_local_users(VMSTest):
    """Can delete local users.

    # https://networkoptix.testrail.net/index.php?/cases/view/115002

    Selection-Tag: users_and_group_management
    Selection-Tag: 115002
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
        viewer_login_2 = 'Viewer2'
        server_vm.api.add_local_viewer(
            username=viewer_login,
            password='ArbitraryPassword',
            )
        server_vm.api.add_local_viewer(
            username=viewer_login_2,
            password='ArbitraryPassword',
            )
        # VMSTest
        main_menu = MainMenu(testkit_api, hid)
        dialog = main_menu.activate_user_management()
        user_settings_dialog = dialog.open_user_settings(viewer_login)

        user_settings_dialog.select_general_tab().start_removing()
        warning_dialog = MessageBox(testkit_api, hid).wait_until_appears()
        warning_dialog.wait_until_has_label('Delete user?')

        warning_dialog.close_by_button('Cancel')
        user_settings_dialog.save_and_close()
        assert dialog.has_user(viewer_login)

        user_settings_dialog = dialog.open_user_settings(viewer_login)
        user_settings_dialog.select_general_tab().start_removing()
        warning_dialog = MessageBox(testkit_api, hid).wait_until_appears()
        warning_dialog.close_by_button('Delete')
        assert not dialog.has_user(viewer_login)

        dialog.select_user(viewer_login_2)
        dialog.start_deleting_selected_rows()
        warning_dialog = MessageBox(testkit_api, hid).wait_until_appears()
        warning_dialog.wait_until_has_label('Delete user?')

        warning_dialog.close_by_button('Cancel')
        assert dialog.has_user(viewer_login_2)

        dialog.start_deleting_selected_rows()
        warning_dialog = MessageBox(testkit_api, hid).wait_until_appears()
        warning_dialog.wait_until_has_label('Delete user?')
        warning_dialog.close_by_button('Delete')
        assert not dialog.has_user(viewer_login_2)


if __name__ == '__main__':
    exit(test_can_delete_local_users().main())
