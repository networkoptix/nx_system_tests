# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timedelta

from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.bookmarks_log import BookmarksLog
from gui.desktop_ui.dialogs.export_settings import ExportSettingsDialog
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineNavigation
from gui.desktop_ui.timeline import TimelineTooltip
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import testcameras_with_archive
from tests.base_test import VMSTest


class test_export_bookmark_to_exe_file(VMSTest):
    """Export bookmark to exe file.

    Open camera with archive, add bookmark, export to exe, open exported file,
    time period in exported file is same as in bookmark

    NOTE: Technically we can't cover 2nd step of the test case.
    See: https://networkoptix.testrail.net/index.php?/cases/view/1684

    Selection-Tag: 1684
    Selection-Tag: export
    Selection-Tag: bookmarks
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        [test_camera_1] = testcameras_with_archive(
            nx_server=server_vm,
            video_file='samples/overlay_test_video.mp4',
            offset_from_now_sec=3600,
            )
        chunk_start = datetime.now()
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        Timeline(testkit_api, hid).create_bookmark_from_interval_context_menu(
            name='bm1',
            description='bm1_descr',
            tags='bm1_tag',
            offset='0',
            width='0.5',
            )
        bookmarks_log = BookmarksLog(testkit_api, hid).open_using_hotkey()
        bookmarks_log.bookmark_by_name('bm1').context_menu("Export Bookmark...")
        ExportSettingsDialog(testkit_api, hid).export_with_specific_path(client_installation.temp_dir() / 'temp_1684.exe')
        bookmarks_log.close()
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('temp_1684.exe')
        local_file_node.open_in_new_tab()
        # Failed due to https://networkoptix.atlassian.net/browse/VMS-52945
        LayoutTabBar(testkit_api, hid).wait_for_open('temp_1684.exe')

        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause_and_to_begin()
        expected_time = datetime.fromisoformat(str(chunk_start)) + timedelta(minutes=0)
        timeline_tooltip = TimelineTooltip(testkit_api)
        timeline_tooltip.wait_for_datetime(expected_time, tolerance=timedelta(seconds=1))

        timeline_navigation.to_end()
        # we created the bookmark with a half of timeline period with 1 hour duration
        expected_time = datetime.fromisoformat(str(chunk_start)) + timedelta(minutes=30)
        timeline_tooltip.wait_for_datetime(expected_time, tolerance=timedelta(seconds=3))


if __name__ == '__main__':
    exit(test_export_bookmark_to_exe_file().main())
