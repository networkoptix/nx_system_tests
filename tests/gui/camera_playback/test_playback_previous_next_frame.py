# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.ocr import ImageDigitsRecognition
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_playback_previous_next_frame(VMSTest):
    """Playback previous next frame.

    # Mediaserver has problems with the b-frames (VMS-27871). Used video without b-frames.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1486

    Selection-Tag: 1486
    Selection-Tag: camera_playback
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        [test_camera_1] = testcameras_with_just_recorded_archive(
            nx_server=server_vm, video_file='samples/frames_test_video_2.mp4')
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        scene = Scene(testkit_api, hid)
        timeline = Timeline(testkit_api, hid)
        timeline.click_at_offset(0.1)
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause()
        ocr_result = ImageDigitsRecognition(scene.first_item_image())
        timeline_navigation.to_previous_frame()
        previous_ocr_result = ImageDigitsRecognition(scene.first_item_image())
        assert ocr_result.compare_ocr_results(previous_ocr_result, -1)

        timeline_navigation.play()
        timeline.click_at_offset(0.1)
        timeline_navigation.pause()
        ocr_result1 = ImageDigitsRecognition(scene.first_item_image())
        timeline_navigation.to_next_frame()
        next_ocr_result = ImageDigitsRecognition(scene.first_item_image())
        assert ocr_result1.compare_ocr_results(next_ocr_result, 1)


if __name__ == '__main__':
    exit(test_playback_previous_next_frame().main())
