# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.ocr import ImageDigitsRecognition
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import testcameras_with_archive
from tests.base_test import VMSTest

_logger = logging.getLogger(__name__)


class test_pause_change_slider_position(VMSTest):
    """Pause and Change slider position.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1537

    Selection-Tag: 1537
    Selection-Tag: camera_playback
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        [test_camera_1] = testcameras_with_archive(
            server_vm, video_file='samples/time_test_video.mp4', offset_from_now_sec=12 * 60)
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.to_prev_chunk()
        time.sleep(5)
        timeline_navigation.pause()
        assert ImageDigitsRecognition(Scene(testkit_api, hid).first_item_image()).has_in_delta_neighborhood(7, 10)
        Timeline(testkit_api, hid).click_at_offset(0.5)
        timeline_navigation.play()
        assert ImageDigitsRecognition(Scene(testkit_api, hid).first_item_image()).has_in_delta_neighborhood(386, 10)


if __name__ == '__main__':
    exit(test_pause_change_slider_position().main())
