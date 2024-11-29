# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MjpegRtspCameraServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.bookmarks_log import BookmarksLog
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_event_bookmark_camera_motion(VMSTest):
    """Motion on camera start and Bookmark for fixed time.

    Add two recording cameras, create event rule to create bookmark at the second camera
    by the motion at the first camera, do the motion at the first camera,
    then wait 1 minute and do the motion again, check two bookmarks are created with expected length.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/77

    Selection-Tag: 77
    Selection-Tag: bookmarks
    Selection-Tag: motion
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        server_vm.allow_license_server_access(license_server.url())
        server_vm.api.set_license_server(license_server.url())
        server_vm.api.activate_license(license_server.generate({
            'QUANTITY2': 1,
            'BRAND2': server_vm.api.get_brand(),
            }))
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        exit_stack.enter_context(playing_testcamera(
            machine_pool,
            server_vm.os_access,
            'samples/overlay_test_video.mp4',
            ))
        rtsp_server = MjpegRtspCameraServer()
        rtsp_server.video_source.stop_motion()
        [rtsp_camera] = add_cameras(server_vm, rtsp_server, indices=[0])
        exit_stack.enter_context(rtsp_server.async_serve())
        [test_camera_2] = server_vm.api.add_test_cameras(0, 1)
        server_vm.api.start_recording(rtsp_camera.id, test_camera_2.id)
        system_administration_dialog = MainMenu(testkit_api, hid).activate_system_administration()
        event_rules_window = system_administration_dialog.open_event_rules()
        rule_dialog = event_rules_window.get_add_rule_dialog()
        event_gui = rule_dialog.get_motion_event()
        event_gui.set_cameras([rtsp_camera.name])
        action_gui = rule_dialog.get_bookmark_action()
        action_gui.set_cameras([test_camera_2.name])
        action_gui.get_fixed_duration_box().type_text('30')
        rule_dialog.save_and_close()
        event_rules_window.close()
        system_administration_dialog.save_and_close()
        rtsp_server.video_source.start_motion()
        time.sleep(10)
        rtsp_server.video_source.stop_motion()
        time.sleep(60)
        rtsp_server.video_source.start_motion()
        time.sleep(60)
        bookmarks_log = BookmarksLog(testkit_api, hid).open_using_hotkey()
        bookmark_data = sorted(
            (b.name(), b.camera(), b.length())
            for b in bookmarks_log.all_bookmarks())
        assert len(bookmark_data) == 2
        rtsp_camera_address = server_vm.os_access.source_address()
        for row in bookmark_data:
            assert f"Motion on {rtsp_camera.name} ({rtsp_camera_address})" in row[0]
            assert test_camera_2.name in row[1]
            [bookmark_length, _] = row[2].split()
            assert 0 <= int(bookmark_length) - 30 < 2


if __name__ == '__main__':
    exit(test_event_bookmark_camera_motion().main())
