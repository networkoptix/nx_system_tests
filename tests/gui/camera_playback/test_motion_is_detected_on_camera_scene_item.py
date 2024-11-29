# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.main_window import MainWindow
from gui.desktop_ui.media_capturing import ImagePiecePercentage
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_motion_is_detected_on_camera_scene_item(VMSTest):
    """Motion is detected on camera scene item.

    Open camera, start recording, enable Smart Search, motion is detected where motion is present,
    check that motion is also detected in archive

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1733

    Selection-Tag: 1733
    Selection-Tag: camera_playback
    Selection-Tag: motion
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/motion_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        testkit_api, camera_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        # same video for multiple cameras
        main_window = MainWindow(testkit_api, hid)
        server_vm.api.start_recording(test_camera_1.id)
        camera_scene_item.activate_button('Motion Search')
        main_window.hover_away()
        scene = Scene(testkit_api, hid)
        assert scene.items()[0].video_is_playing()
        assert _motion_mask_is_displayed(camera_scene_item)

        time.sleep(30)
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause_and_to_begin()
        time.sleep(2)
        timeline_navigation.play()
        main_window.hover_away()
        assert scene.items()[0].video_is_playing()
        assert _motion_mask_is_displayed(camera_scene_item)


def _motion_mask_is_displayed(camera_scene_item) -> bool:
    # works only when special motion test video is played
    # it must be grayscale and only right part of video should contain motion
    timeout_at = time.monotonic() + 10
    while True:
        video = camera_scene_item.video_with_fixed_length(10)
        right_part = video.crop_percentage(ImagePiecePercentage(0.5, 0, 0.5, 1))
        left_part = video.crop_percentage(ImagePiecePercentage(0, 0, 0.5, 1))
        if not left_part.has_motion_mask() and right_part.has_motion_mask():
            return True
        if time.monotonic() > timeout_at:
            return False
        time.sleep(1)


if __name__ == '__main__':
    exit(test_motion_is_detected_on_camera_scene_item().main())
