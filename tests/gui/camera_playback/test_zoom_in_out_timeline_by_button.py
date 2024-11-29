# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from mediaserver_scenarios.testcamera_setup import testcameras_with_archive
from tests.base_test import VMSTest

_logger = logging.getLogger(__name__)


class test_zoom_in_out_timeline_by_button(VMSTest):
    """Zoom in out timeline by button.

    Open camera with recorded data, click on "+" button on timeline, click on "-" button on timeline

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1567

    Selection-Tag: 1567
    Selection-Tag: camera_playback
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        video_file = 'samples/time_test_video.mp4'
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, video_file))
        [test_camera_1] = testcameras_with_archive(
            server_vm, video_file=video_file, offset_from_now_sec=24 * 3600)
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        timeline = Timeline(testkit_api, hid)
        width_initial = timeline.get_page_step()
        _logger.debug("Initial width", str(width_initial))
        timeline.zoom_in_using_plus_button()
        width_zoomed_in = timeline.get_page_step()
        _logger.debug("Zoomed in width", str(width_zoomed_in))
        assert width_initial > width_zoomed_in
        timeline.zoom_out_using_minus_button()
        width_zoomed_out = timeline.get_page_step()
        _logger.debug("Zoomed out width", str(width_zoomed_out))
        assert width_zoomed_in < width_zoomed_out


if __name__ == '__main__':
    exit(test_zoom_in_out_timeline_by_button().main())