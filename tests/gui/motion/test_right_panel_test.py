# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from distrib import BranchNotSupported
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_scenarios import DesktopMachinePool
from gui.desktop_ui.right_panel_widget import RightPanelWidget
from gui.desktop_ui.right_panel_widget.notifications_ribbon import NotificationsRibbon
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_api import MotionType
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_right_panel_test(VMSTest):
    """Right panel tabs.

    Create rule - generic event to notification. Trigger and check result in Notifications Ribbon.
    Check that if motion is enabled, red chunks appear, motion tab is not empty
    and scene item Motion Search button works fine.
    Check that bookmark is saved and is shown correctly in bookmarks tab.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/91602
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/50
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1452

    Selection-Tag: 91602
    Selection-Tag: 50
    Selection-Tag: 1452
    Selection-Tag: bookmarks
    Selection-Tag: motion
    Selection-Tag: event_rules
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            raise BranchNotSupported("Test should be fixed for VMS 6.1+")

        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        server_vm = exit_stack.enter_context(machine_pool.setup_one_server())
        vm_pool_client = DesktopMachinePool(
            get_run_dir() / 'client', ClassicInstallerSupplier(args.distrib_url))
        client_stand = exit_stack.enter_context(vm_pool_client.client_stand())
        client_stand.set_screen_resolution(1920, 1080, 32)
        exit_stack.enter_context(client_stand.get_screen_recorder().record_video(get_run_dir()))
        # same video for multiple cameras
        video_file = 'samples/dynamic_test_video.mp4'
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, video_file))
        [test_camera_1] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file=video_file,
            )
        server_vm.api.set_motion_type_for_cameras([test_camera_1.id], MotionType.DEFAULT)
        server_vm.api.start_recording(test_camera_1.id)
        testkit_api, camera_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_stand.installation(),
            server_vm,
            test_camera_1.name,
            )
        hid = HID(testkit_api)
        right_panel = RightPanelWidget(testkit_api, hid)

        event_rules_window = right_panel.open_event_rules()
        rule_dialog = event_rules_window.get_add_rule_dialog()
        rule_dialog.get_generic_event()
        action_gui = rule_dialog.get_desktop_notification_action()
        action_gui.set_all_users()
        rule_dialog.save_and_close()
        event_rules_window.close()
        bm_name = 'bm1_camera1'
        bm_description = 'bmdescr'
        first_bookmark_started_at = int(server_vm.api.get_datetime().timestamp() * 1000)
        server_vm.api.add_bookmark(
            camera_id=test_camera_1.id,
            name=bm_name,
            start_time_ms=first_bookmark_started_at,
            duration_ms=1000,
            description=bm_description,
            )
        server_vm.api.create_event(
            source='device1',
            caption='Door has been opened',
            description='This event may occur if sbd opens the door on the first floor',
            )
        tile = NotificationsRibbon(testkit_api, hid).wait_for_notification('Door has been opened')
        assert tile.get_description() == 'This event may occur if sbd opens the door on the first floor'

        right_panel.open_motion_tab()
        timeline = Timeline(testkit_api, hid)
        assert camera_scene_item.button_checked('Motion Search')
        assert test_camera_1.name in right_panel.motion_tab.camera_filter_value()
        assert right_panel.motion_tab.has_events_for(test_camera_1.name)
        # TODO: Need to fix in VMS 6.1+
        assert timeline.get_red_chunks()

        right_panel.open_bookmarks_tab()
        assert not timeline.get_red_chunks()
        right_panel.bookmarks_tab.wait_for_bookmark(bm_name, bm_description)

        camera_scene_item.activate_button('Motion Search')
        assert camera_scene_item.button_checked('Motion Search')
        assert right_panel.motion_tab.has_events_for(test_camera_1.name)

        right_panel.open_events_tab()
        assert 'Generic Event', 'Server Started' in right_panel.events_tab.get_event_names()

        right_panel.open_motion_tab_using_hotkey()
        assert right_panel.motion_tab.has_events_for(test_camera_1.name)


if __name__ == '__main__':
    exit(test_right_panel_test().main())
