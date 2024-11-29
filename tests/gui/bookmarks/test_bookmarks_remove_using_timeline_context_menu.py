# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest
from tests.waiting import wait_for_truthy


class test_bookmarks_remove_using_timeline_context_menu(VMSTest):
    """Remove bookmark using timeline context menu.

    Create bookmark, verify existence, remove.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/59

    Selection-Tag: 59
    Selection-Tag: bookmarks
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            camera_count=1,
            video_file='samples/overlay_test_video.mp4',
            )
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        timeline = Timeline(testkit_api, hid)
        bookmark = timeline.create_bookmark_from_interval_context_menu(
            name='bm1',
            description='bm1_descr',
            tags='bm1_tag',
            offset='0',
            width='0.5',
            )
        wait_for_truthy(bookmark.exists, description='Bookmark exists', timeout_sec=10)
        bookmark.remove_using_context_menu()
        timeline.click_at_offset(0.9)
        wait_for_truthy(lambda: not bookmark.exists(), description='Bookmark not exists', timeout_sec=10)


if __name__ == '__main__':
    exit(test_bookmarks_remove_using_timeline_context_menu().main())
