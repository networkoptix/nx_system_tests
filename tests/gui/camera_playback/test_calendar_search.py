# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import timedelta

from directories import get_run_dir
from distrib import BranchNotSupported
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.nx_calendar import DayTimeCalendar
from gui.desktop_ui.nx_calendar import MonthCalendar
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_calendar_search(VMSTest):
    """Calendar search.

    Choose cameras with archive for current hour and another with archives for previous days and
    previous hours during this day. Check appropriate calendar color for different timeframes
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1530

    Selection-Tag: 1530
    Selection-Tag: camera_playback
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            raise BranchNotSupported("Test should be fixed for VMS 6.1+")

        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4', 2))
        [test_camera_1, test_camera_2] = server_vm.api.add_test_cameras(0, 2)
        camera_1_archive = server_vm.default_archive().camera_archive(test_camera_1.physical_id)
        machine_now = server_vm.os_access.get_datetime()
        server_vm.api.enable_recording(test_camera_1.id)
        camera_1_archive.high().add_fake_record(
            start_time=(machine_now - timedelta(days=2)),
            duration_sec=timedelta(days=2).total_seconds(),
            bitrate_bps=8,
            )
        server_vm.api.rebuild_main_archive()
        rtree = ResourceTree(testkit_api, hid)
        camera_1_scene_item = rtree.get_camera(test_camera_1.name).open()
        month_calendar = MonthCalendar(testkit_api, hid)
        month_calendar.show()
        # The safest way is to check the previous day's cell.
        calendar_cell = month_calendar.day_cell(machine_now - timedelta(days=1))
        # TODO: Need to fix in VMS 6.1+
        assert calendar_cell.wait_for_indication('primary archive')
        camera_2_scene_item = rtree.get_camera(test_camera_2.name).open()
        assert calendar_cell.wait_for_indication('secondary archive')

        month_calendar.day_cell(machine_now).click()
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause()
        # Length of timeline is equal to time passed since beginning of current day.
        timeline = Timeline(testkit_api, hid)
        current_length = timeline.get_current_length()
        machine_now = server_vm.os_access.get_datetime()
        delta1 = abs(current_length - timedelta(hours=machine_now.hour, minutes=machine_now.minute))
        delta2 = abs(current_length - timedelta(hours=24, minutes=machine_now.minute))  # Prevent error at 00:00
        assert delta1 < timedelta(minutes=1) or delta2 < timedelta(minutes=1)

        day_calendar = DayTimeCalendar(testkit_api, hid)
        # The safest way is to check the previous hour's cell.
        hour_cell = day_calendar.hour_cell(machine_now - timedelta(hours=1))
        camera_1_scene_item.click()
        assert hour_cell.wait_for_indication('primary archive')
        camera_2_scene_item.click()
        assert hour_cell.wait_for_indication('secondary archive')

        day_calendar.hour_cell(machine_now).click()
        timeline_navigation.pause()
        # Length of timeline is equal to time passed since beginning of current hour.
        current_length = timeline.get_current_length()
        machine_now = server_vm.os_access.get_datetime()
        delta3 = abs(current_length - timedelta(minutes=machine_now.minute))
        delta4 = abs(current_length - timedelta(hours=1, minutes=machine_now.minute))  # Prevent error at XX:00
        assert delta3 < timedelta(minutes=1) or delta4 < timedelta(minutes=1)


if __name__ == '__main__':
    exit(test_calendar_search().main())
