# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import cast

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.messages import MessageBox
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_api import MediaserverApiV3
from tests.base_test import VMSTest


class test_can_delete_custom_user_group(VMSTest):
    """Can delete custom group.

    # https://networkoptix.testrail.net/index.php?/cases/view/115005

    Selection-Tag: users_and_group_management
    Selection-Tag: 115005
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())  # Background and scenario
        # Background
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        admin_name = 'root'
        api = cast(MediaserverApiV3, server_vm.api)
        user = api.add_local_admin(admin_name, 'WellKnownPassword2')
        group_name = 'Test'
        group_name_2 = 'Test2'
        group_id = api.add_user_group(group_name, ['none'])
        group_id_2 = api.add_user_group(group_name_2, ['none'])
        api.add_user_to_group(user.id, group_id)
        api.add_user_to_group(user.id, group_id_2)
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
        group_settings_dialog.get_general_tab().start_removing()
        warning_dialog = MessageBox(testkit_api, hid).wait_until_appears()
        warning_dialog.wait_until_has_label('Delete group?')

        warning_dialog.close_by_button('Cancel')
        group_settings_dialog.save_and_close()
        assert dialog.has_group(group_name)

        group_settings_dialog = dialog.open_group_settings(group_name)
        group_settings_dialog.get_general_tab().start_removing()
        warning_dialog = MessageBox(testkit_api, hid).wait_until_appears()
        warning_dialog.close_by_button('Delete')
        assert not dialog.has_group(group_name)
        assert dialog.get_user_data_by_name(user.name)['groups'] == f'Power Users, {group_name_2}'

        dialog.select_group(group_name_2)
        dialog.start_deleting_selected_rows()
        warning_dialog = MessageBox(testkit_api, hid).wait_until_appears()
        warning_dialog.wait_until_has_label('Delete group?')

        warning_dialog.close_by_button('Cancel')
        assert dialog.has_group(group_name_2)

        dialog.start_deleting_selected_rows()
        warning_dialog = MessageBox(testkit_api, hid).wait_until_appears()
        warning_dialog.wait_until_has_label('Delete group?')
        warning_dialog.close_by_button('Delete')
        assert not dialog.has_group(group_name_2)


if __name__ == '__main__':
    exit(test_can_delete_custom_user_group().main())
