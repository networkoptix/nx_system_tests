# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import TimelineControlWidget
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_pause_play_live(VMSTest):
    """Pause and Play on live.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1481

    Selection-Tag: 1481
    Selection-Tag: camera_playback
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/dynamic_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        scene = Scene(testkit_api, hid)
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause()
        assert not scene.items()[0].video_is_playing()

        time.sleep(70)
        timeline_navigation.play()
        assert scene.items()[0].video_is_playing()
        assert TimelineControlWidget(testkit_api, hid).live_button.is_checked()


if __name__ == '__main__':
    exit(test_pause_play_live().main())
