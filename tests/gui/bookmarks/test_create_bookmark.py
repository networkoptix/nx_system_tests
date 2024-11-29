# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.bookmarks_log import BookmarksLog
from gui.desktop_ui.right_panel_widget import RightPanelWidget
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_create_bookmark(VMSTest):
    """Create bookmark from timeline.

    Record an archive, create a bookmark, check bookmark tab is open,
    name and description of the bookmark are expected in bookmark thumbnail,
    name and tag of the bookmark are expected in bookmark log,
    delete created bookmark.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/50

    Selection-Tag: 50
    Selection-Tag: bookmarks
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        [test_camera_1] = testcameras_with_just_recorded_archive(
            nx_server=server_vm, video_file='samples/overlay_test_video.mp4')
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        Timeline(testkit_api, hid).create_bookmark_from_interval_context_menu(
            name='bmname',
            description='bmdescr',
            tags='bmtag',
            offset='0.1',
            width='0.5',
            )
        # Wait for bookmark tab to open and bookmark to appear in it.
        right_panel = RightPanelWidget(testkit_api, hid)
        right_panel.open_bookmarks_tab()
        assert right_panel.bookmarks_tab.is_open()
        # Tags don't display on the right panel, so we don't check.
        assert right_panel.bookmarks_tab.has_bookmark('bmname', 'bmdescr')
        bookmarks_log = BookmarksLog(testkit_api, hid).open_using_hotkey()
        bookmark_data = sorted(
            (b.name(), b.tags())
            for b in bookmarks_log.all_bookmarks())
        assert ('bmname', 'bmtag') in bookmark_data


if __name__ == '__main__':
    exit(test_create_bookmark().main())
