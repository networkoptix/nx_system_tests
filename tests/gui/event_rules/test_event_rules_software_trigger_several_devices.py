# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from uuid import UUID

from directories import get_run_dir
from distrib import BranchNotSupported
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.right_panel_widget.notifications_ribbon import NotificationsRibbon
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_event_rules_software_trigger_several_devices(VMSTest):
    """Event rules software trigger several devices.

    Create rule - software trigger to notification. Check that button exists on multiple
    selected cameras.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/15709

    Selection-Tag: 15709
    Selection-Tag: event_rules
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            raise BranchNotSupported("Test should be fixed for VMS 6.1+")

        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        # Disable rules 'On Network Issue' as the event may appear and displace test events.
        event_rules = server_vm.api.list_event_rules()
        for rule in event_rules:
            if rule.data['eventType'] == 'networkIssueEvent':
                server_vm.api.disable_event_rule(UUID(rule.data['id']))
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        # same video for multiple cameras
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/dynamic_test_video.mp4', 2))
        [test_camera_1, test_camera_2] = server_vm.api.add_test_cameras(0, 2)
        system_administration_dialog = MainMenu(testkit_api, hid).activate_system_administration()
        event_rules_window = system_administration_dialog.open_event_rules()
        rule_dialog = event_rules_window.get_add_rule_dialog()
        event_gui = rule_dialog.get_soft_trigger_event()
        event_gui.get_software_trigger_name_field().type_text('test trigger')
        # TODO: Need to fix in VMS 6.1+
        event_gui.set_cameras([test_camera_1.name, test_camera_2.name])
        event_gui.set_all_users()
        action_gui = rule_dialog.get_desktop_notification_action()
        action_gui.set_all_users()
        action_gui.get_interval_of_action_checkbox().set(False)
        rule_dialog.save_and_close()
        event_rules_window.close()
        system_administration_dialog.save_and_close()
        rtree = ResourceTree(testkit_api, hid)
        camera_1_scene_item = rtree.get_camera(test_camera_1.name).open()
        camera_2_scene_item = rtree.get_camera(test_camera_2.name).open()
        assert camera_1_scene_item.has_soft_trigger_button()
        assert camera_2_scene_item.has_soft_trigger_button()

        ribbon = NotificationsRibbon(testkit_api, hid)
        # Each tile may take up to 5 seconds to handle, and it's better to close unused ones.
        ribbon.close_all_tiles()
        hid.mouse_left_click_on_object(camera_1_scene_item.get_soft_trigger_button())
        tile = ribbon.wait_for_notification('Soft Trigger test trigger', resource_name=test_camera_1.name)
        assert 'Soft Trigger' in tile.get_html_name()
        tile.close()
        hid.mouse_left_click_on_object(camera_2_scene_item.get_soft_trigger_button())
        tile = ribbon.wait_for_notification('Soft Trigger test trigger', resource_name=test_camera_2.name)
        assert 'Soft Trigger' in tile.get_html_name()


if __name__ == '__main__':
    exit(test_event_rules_software_trigger_several_devices().main())
