# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_api import Groups
from tests.base_test import VMSTest


class test_excluding_custom_group_from_predefined_group(VMSTest):
    """Excluding custom group from predefined group.

    # https://networkoptix.testrail.net/index.php?/cases/view/115057

    Selection-Tag: users_and_group_management
    Selection-Tag: 115057
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())  # Background and scenario
        # Background
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        group_name = 'Test Group'
        server_vm.api.add_user_group(group_name, ['none'], [Groups.LIVE_VIEWERS])
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        # VMSTest
        dialog = MainMenu(testkit_api, hid).activate_user_management()
        group_settings_dialog_1 = dialog.open_group_settings(group_name)
        general_tab = group_settings_dialog_1.get_general_tab()
        general_tab.exclude_group('Live Viewers')
        assert general_tab.get_permission_groups() == []

        groups_tab = group_settings_dialog_1.get_groups_tab()
        assert groups_tab.selected_groups_count() == 0
        assert not groups_tab.has_existing_groups()
        assert groups_tab.get_main_placeholder_text() == 'No groups'
        assert groups_tab.get_additional_placeholder_text() == 'Use controls on the left to add to a group'
        group_settings_dialog_1.save_and_close()
        assert dialog.get_group_data_by_name(group_name)['member_of'] == ''

        permissions_tab = dialog.open_group_settings(group_name).get_resources_tab()
        assert permissions_tab.get_resources_with_active_permissions() == []


if __name__ == '__main__':
    exit(test_excluding_custom_group_from_predefined_group().main())
