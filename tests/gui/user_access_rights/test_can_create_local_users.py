# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_can_create_local_users(VMSTest):
    """Can create local users.

    # https://networkoptix.testrail.net/index.php?/cases/view/114998

    Selection-Tag: users_and_group_management
    Selection-Tag: 114998
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

        general_tab = new_user_dialog.general_tab()
        viewer_login = 'Viewer'
        general_tab.set_login(viewer_login)
        viewer_password = 'ArbitraryPassword'
        general_tab.set_password(viewer_password)
        temp_viewer_group = 'Power Users'
        general_tab.set_group(temp_viewer_group)
        general_tab.wait_until_group_selected(temp_viewer_group)

        groups_tab = new_user_dialog.groups_tab()
        assert groups_tab.get_selected_group_names() == [temp_viewer_group]
        viewer_group = 'Viewers'
        groups_tab.set_several_groups([viewer_group])
        new_user_dialog.general_tab().wait_until_group_selected(viewer_group)

        new_user_dialog.save()
        user_data = dialog.get_user_data_by_name(viewer_login)
        assert user_data['groups'] == viewer_group

        main_menu.disconnect_from_server()
        address, port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        main_menu.activate_connect_to_server().connect(
            address=address,
            user=viewer_login,
            password=viewer_password,
            port=port,
            )
        ResourceTree(testkit_api, hid).wait_for_current_user()


if __name__ == '__main__':
    exit(test_can_create_local_users().main())
