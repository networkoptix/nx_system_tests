# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineControlWidget
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_pause_sync(VMSTest):
    """Pause and Sync and change layouts.

    Create Layout1 with one recording camera, create Layout2 with two recording cameras,
    open layouts, press pause for playback at Layout1, open Layout2 and disable sync, start
    playback, open Layout1, check video is paused; open Layout2, check playback is on and
    synchronization is disabled.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/934

    Selection-Tag: 934
    Selection-Tag: layouts
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        # same video for multiple cameras
        video_file = 'samples/time_test_video.mp4'
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, video_file, 2))
        [test_camera_1, test_camera_2] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file=video_file,
            camera_count=2,
            )
        server_vm.api.start_recording(test_camera_1.id, test_camera_2.id)
        testkit_api, camera_1_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name, layout_name='Layout1')
        hid = HID(testkit_api)
        layout_tab_bar = LayoutTabBar(testkit_api, hid)
        layout_tab_bar.save('Layout1')
        camera_2_scene_item = ResourceTree(testkit_api, hid).get_camera(test_camera_2.name).open()
        camera_2_scene_item.wait_for_accessible()
        layout_tab_bar.save_current_as('Layout2')
        rtree = ResourceTree(testkit_api, hid)
        rtree.get_layout('Layout1').open()
        timeline = Timeline(testkit_api, hid)
        timeline.click_at_offset(0.2)
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause()
        rtree.get_layout('Layout2').open()
        timeline_control_widget = TimelineControlWidget(testkit_api, hid)
        timeline_control_widget.synchronize_streams_button.set(False)
        timeline.click_at_offset(0.2)
        rtree.get_layout('Layout1').open()
        assert not camera_1_scene_item.video_is_playing()
        rtree.get_layout('Layout2').open()
        assert not timeline_control_widget.synchronize_streams_button.is_checked()
        assert 'Pause' in timeline_navigation.get_playback_button_tooltip_text()
        timeline_control_widget.wait_for_live_button_unchecked()
        camera_1_scene_item.click()
        assert timeline_control_widget.live_button.is_checked()


if __name__ == '__main__':
    exit(test_pause_sync().main())
