# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_including_custom_group_to_predefined_group(VMSTest):
    """Including custom group to predefined group.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/115056

    Selection-Tag: users_and_group_management
    Selection-Tag: 115056
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())  # Background and scenario
        # Background
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
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
        group_settings_dialog_1 = dialog.open_group_settings(group_name)
        groups_tab = group_settings_dialog_1.get_groups_tab()
        groups_tab.select_group('Live Viewers')
        group_settings_dialog_1.click_apply_button()
        [membership_group] = groups_tab.get_existing_group_names()
        assert membership_group == 'Live Viewers'
        general_tab = group_settings_dialog_1.get_general_tab()
        [permission_group] = general_tab.get_permission_groups()
        assert permission_group == 'Live Viewers'

        groups_tab = group_settings_dialog_1.get_groups_tab()
        groups_tab.unselect_group('Live Viewers')
        groups_tab.select_group('Viewers')
        [membership_group] = groups_tab.get_existing_group_names()
        assert membership_group == 'Viewers'
        general_tab = group_settings_dialog_1.get_general_tab()
        [permission_group] = general_tab.get_permission_groups()
        assert permission_group == 'Viewers'
        group_settings_dialog_1.save_and_close()

        group_settings_dialog_2 = dialog.open_group_settings(group_name)
        resource_tab = group_settings_dialog_2.get_resources_tab()
        group_permissions = resource_tab.get_resource('Cameras & Devices').get_active_permissions()
        if server_vm.api.server_newer_than('vms_6.0'):
            expected_permissions = ['View Live', 'Play Audio', 'View Archive', 'Export Archive', 'View Bookmarks']
        else:
            expected_permissions = ['View Live', 'View Archive', 'Export Archive', 'View Bookmarks']
        assert group_permissions == expected_permissions, f'Actual: {group_permissions}, Expected: {expected_permissions}'

        cell = resource_tab.get_resource('Cameras & Devices').permission('View Live')
        # Instant mouse movements cause tooltip instability. Add extra moves for stability.
        cell_center = cell.bounds().center()
        hid.mouse_move(cell_center)
        hid.mouse_move(cell_center.up(5))
        hid.mouse_move(cell_center)
        tooltip_text = resource_tab.get_tooltip_text()
        expected_tooltip_text = 'Add <b>View Live</b> permission<br><br>Already inherited from <b>Viewers</b> group'
        assert tooltip_text == expected_tooltip_text, f'Actual: {tooltip_text}, Expected: {expected_tooltip_text}'


if __name__ == '__main__':
    exit(test_including_custom_group_to_predefined_group().main())
