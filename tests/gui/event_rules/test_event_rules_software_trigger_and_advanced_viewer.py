# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server_as_user
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.right_panel_widget.notifications_ribbon import NotificationsRibbon
from gui.gui_test_stand import GuiTestStand
from gui.server_login_steps import _log_in_using_main_menu
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_event_rules_software_trigger_and_advanced_viewer(VMSTest):
    """Event rules software trigger and advanced viewer.

    Create rule - software trigger to notification. Check that button exists only for
    selected users.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/15703
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/15706

    Selection-Tag: 15703
    Selection-Tag: 15706
    Selection-Tag: event_rules
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/dynamic_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        server_vm.api.add_local_admin('TestAdmin', 'WellKnownPassword2')
        server_vm.api.add_local_advanced_viewer('AdvancedViewer', 'WellKnownPassword2')
        address_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        client_unit = start_desktop_client_connected_to_server_as_user(
            address_port,
            machine_pool.get_testkit_port(),
            client_installation, 'TestAdmin', 'WellKnownPassword2')
        system_administration_dialog = MainMenu(client_unit.testkit(), client_unit.hid()).activate_system_administration()
        event_rules_window = system_administration_dialog.open_event_rules()
        rule_dialog = event_rules_window.get_add_rule_dialog()
        event_gui = rule_dialog.get_soft_trigger_event()
        event_gui.get_software_trigger_name_field().type_text('test trigger')
        event_gui.set_users_with_groups('Advanced Viewers')
        action_gui = rule_dialog.get_desktop_notification_action()
        action_gui.set_all_users()
        rule_dialog.save_and_close()
        event_rules_window.close()
        system_administration_dialog.save_and_close()
        camera_scene_item_1 = ResourceTree(client_unit.testkit(), client_unit.hid()).get_camera(test_camera_1.name).open()
        assert not camera_scene_item_1.has_soft_trigger_button()

        _log_in_using_main_menu(client_unit.testkit(), client_unit.hid(), address_port, 'AdvancedViewer', 'WellKnownPassword2')
        camera_scene_item_2 = ResourceTree(client_unit.testkit(), client_unit.hid()).get_camera(test_camera_1.name).open()
        assert camera_scene_item_2.has_soft_trigger_button()
        client_unit.hid().mouse_left_click_on_object(camera_scene_item_2.get_soft_trigger_button())
        NotificationsRibbon(client_unit.testkit(), client_unit.hid()).wait_for_notification('Soft Trigger test trigger')


if __name__ == '__main__':
    exit(test_event_rules_software_trigger_and_advanced_viewer().main())
