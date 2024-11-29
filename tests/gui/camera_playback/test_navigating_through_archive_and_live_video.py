# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.ocr import ImageTextRecognition
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineControlWidget
from gui.desktop_ui.timeline import TimelinePlaceholder
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_navigating_through_archive_and_live_video(VMSTest):
    """Navigating through archive and live video.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1494

    Selection-Tag: 1494
    Selection-Tag: camera_playback
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/dynamic_test_video.mp4', 2))
        [test_camera_2] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file='samples/time_test_video.mp4',
            )
        [test_camera_1] = server_vm.api.add_test_cameras(1, 1)
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_2.name)
        hid = HID(testkit_api)
        timeline_control_widget = TimelineControlWidget(testkit_api, hid)
        assert timeline_control_widget.live_button.is_checked()
        assert timeline_control_widget.synchronize_streams_button.is_checked()

        Timeline(testkit_api, hid).click_at_offset(0.1)
        rtree = ResourceTree(testkit_api, hid)
        camera_scene_item = rtree.get_camera(test_camera_1.name).drag_n_drop_on_scene()
        camera_scene_item.wait_for_accessible()
        text_comparer = ImageTextRecognition(camera_scene_item.image_capture())
        assert text_comparer.has_line('NO DATA')
        timeline_control_widget.wait_for_live_button_unchecked()

        rtree.get_camera(test_camera_2.name).remove()
        camera_scene_item.wait_for_accessible()
        assert Scene(testkit_api, hid).items()[0].video_is_playing()
        assert TimelinePlaceholder(testkit_api).get_camera_name() == test_camera_1.name
        assert timeline_control_widget.live_button.is_checked()
        assert not ResourceTree(testkit_api, hid).get_server(server_vm.api.get_server_name()).has_camera(test_camera_2.name)


if __name__ == '__main__':
    exit(test_navigating_through_archive_and_live_video().main())
