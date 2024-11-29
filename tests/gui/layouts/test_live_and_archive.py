# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import timedelta

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import CameraSceneItem
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineControlWidget
from gui.desktop_ui.timeline import TimelineNavigation
from gui.desktop_ui.timeline import TimelineTooltip
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_live_and_archive(VMSTest):
    """Live video and archive.

    Create Layout1 with one recording camera, create Layout2 with two recording cameras,
    open layouts, choose position in archive for layout1, check archive is played;
    open Layout2 and check live streams play; open Layout1 and check video plays
    from the same position.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/932

    Selection-Tag: 932
    Selection-Tag: layouts
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        # same video for multiple cameras
        video_file = 'samples/time_test_video.mp4'
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, video_file, 2))
        [test_camera_1, test_camera_2] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file=video_file,
            camera_count=2,
            )
        server_vm.api.start_recording(test_camera_1.id, test_camera_2.id)
        rtree = ResourceTree(testkit_api, hid)
        rtree.get_camera(test_camera_1.name).open()
        layout_tab_bar = LayoutTabBar(testkit_api, hid)
        layout_tab_bar.save_current_as('Layout1')
        rtree.get_camera(test_camera_2.name).open()
        layout_tab_bar.save_current_as('Layout2')
        rtree = ResourceTree(testkit_api, hid)
        rtree.get_layout('Layout1').open()
        Timeline(testkit_api, hid).click_at_offset(0.1)
        timeline_control_widget = TimelineControlWidget(testkit_api, hid)
        timeline_control_widget.wait_for_live_button_unchecked()
        assert 'Pause' in TimelineNavigation(testkit_api, hid).get_playback_button_tooltip_text()
        timeline_tooltip_positions = []
        timeline_tooltip = TimelineTooltip(testkit_api)
        timeline_tooltip_positions.append(timeline_tooltip.date_time())
        rtree.get_layout('Layout2').open()
        CameraSceneItem(testkit_api, hid, test_camera_1.name).wait_for_accessible()
        CameraSceneItem(testkit_api, hid, test_camera_2.name).wait_for_accessible()
        assert timeline_control_widget.live_button.is_checked()

        rtree.get_layout('Layout1').open()
        CameraSceneItem(testkit_api, hid, test_camera_1.name).wait_for_accessible()
        tolerance = timedelta(seconds=10)
        timeline_tooltip.verify_datetime(
            timeline_tooltip_positions[-1],
            tolerance=tolerance,
            )


if __name__ == '__main__':
    exit(test_live_and_archive().main())
