# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MjpegRtspCameraServer
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineControlWidget
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.base_test import VMSTest


class test_3_seconds_recording_camera(VMSTest):
    """Last 3 seconds playback of recording camera.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1890

    Selection-Tag: 1890
    Selection-Tag: camera_playback
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        server_vm.allow_license_server_access(license_server.url())
        server_vm.api.set_license_server(license_server.url())
        server_vm.api.activate_license(license_server.generate({
            'QUANTITY2': 1,
            'BRAND2': server_vm.api.get_brand(),
            }))
        rtsp_server = MjpegRtspCameraServer()
        [rtsp1] = add_cameras(server_vm, rtsp_server, indices=[0])
        exit_stack.enter_context(rtsp_server.async_serve())
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, rtsp1.name)
        hid = HID(testkit_api)
        server_vm.api.start_recording(rtsp1.id)
        time.sleep(20)
        # Position of last 3 seconds for 20-seconds archive.
        Timeline(testkit_api, hid).click_at_offset(0.95)
        # Waiting for slider moves back several seconds, sometimes 3 seconds are not enough.
        time.sleep(6)
        assert 'Pause' in TimelineNavigation(testkit_api, hid).get_playback_button_tooltip_text()
        TimelineControlWidget(testkit_api, hid).wait_for_live_button_unchecked()


if __name__ == '__main__':
    exit(test_3_seconds_recording_camera().main())
