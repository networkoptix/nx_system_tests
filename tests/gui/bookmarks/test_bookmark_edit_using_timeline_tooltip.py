# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.right_panel_widget import RightPanelWidget
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest
from tests.waiting import wait_for_truthy


class test_bookmark_edit_using_timeline_tooltip(VMSTest):
    """Edit bookmark from bookmarks tooltip.

    Create bookmark, edit, verify.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/89

    Selection-Tag: 89
    Selection-Tag: bookmarks
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
        bookmark.edit_using_tooltip('bm1_edit', 'bm1_descr_edit', 'bm1_tag_edit')
        bookmark.verify('bm1_edit', 'bm1_descr_edit', 'bm1_tag_edit')
        # Tags don't display on the right panel, so we don't check.
        right_panel = RightPanelWidget(testkit_api, hid)
        right_panel.open_bookmarks_tab()
        assert right_panel.bookmarks_tab.has_bookmark('bm1_edit', 'bm1_descr_edit')


if __name__ == '__main__':
    exit(test_bookmark_edit_using_timeline_tooltip().main())
