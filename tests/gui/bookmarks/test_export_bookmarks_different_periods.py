# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.bookmarks_log import BookmarksLog
from gui.desktop_ui.dialogs.export_settings import ExportSettingsDialog
from gui.desktop_ui.dialogs.export_settings import MultiExportSettings
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.main_window import MainWindow
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.ocr import ImageTextRecognition
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_export_bookmarks_different_periods(VMSTest):
    """Export bookmarks for different periods.

    Create two bookmarks at two cameras (1 at 1) with the different not overlapped periods,
    open bookmark log, select the both bookmarks, export them as nov-file,
    open exported file at the scene, check time periods are the same as in bookmarks,
    playback is started from an earlier recording, at this time, one camera displays video,
    but the other displays NO DATA, after the end of the first bookmark, playback goes to the second
    bookmark, at this time, the first camera displays NO DATA, but the other displays video.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/56719

    Selection-Tag: 56719
    Selection-Tag: export
    Selection-Tag: bookmarks
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4', 2))
        [test_camera_1, test_camera_2] = server_vm.api.add_test_cameras(0, 2)
        media_file = SampleMediaFile(gui_prerequisite_store.fetch('samples/overlay_test_video.mp4'))
        start_time_1 = datetime.now(timezone.utc) - timedelta(minutes=6)
        start_time_2 = datetime.now(timezone.utc) - timedelta(minutes=3)
        server_vm.default_archive().camera_archive(test_camera_1.physical_id).save_media_sample(
            start_time_1,
            media_file,
            )
        server_vm.default_archive().camera_archive(test_camera_2.physical_id).save_media_sample(
            start_time_2,
            media_file,
            )
        server_vm.api.rebuild_main_archive()
        testkit_api, camera_1_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        timeline = Timeline(testkit_api, hid)
        timeline.create_bookmark_from_interval_context_menu(
            name='bmname1',
            description='bmdescr',
            tags='bmtag',
            offset='0',
            width='0.03',
            )
        camera_2_scene_item = ResourceTree(testkit_api, hid).get_camera(test_camera_2.name).open_in_new_tab()
        camera_2_scene_item.wait_for_accessible()
        timeline.create_bookmark_from_interval_context_menu(
            name='bmname2',
            description='bmdescr',
            tags='bmtag',
            offset='0',
            width='0.03',
            )
        bookmarks_log = BookmarksLog(testkit_api, hid).open_using_hotkey()
        bookmarks_table = bookmarks_log.get_table()
        bookmarks_table.row(0).leftmost_cell().click()
        bookmarks_table.row(1).leftmost_cell().ctrl_click()
        [row0, row1] = bookmarks_table.all_rows()
        assert row0.is_selected()
        assert row1.is_selected()
        row0.leftmost_cell().context_menu("Export Bookmarks...")
        assert MultiExportSettings(testkit_api, hid).is_open()
        export_settings = ExportSettingsDialog(testkit_api, hid)
        assert not export_settings.has_tab('Single Video')

        export_settings.export_with_specific_path(client_installation.temp_dir() / 'temp_56719.nov')
        bookmarks_log.close()
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('temp_56719.nov')
        local_file_node.open_in_new_tab()
        LayoutTabBar(testkit_api, hid).wait_for_open('temp_56719.nov')

        MainWindow(testkit_api, hid).hover_away()
        assert camera_1_scene_item.image_capture().is_similar_to(SavedImage(gui_prerequisite_store.fetch('test56719/playback.png')))
        text_comparer = ImageTextRecognition(camera_2_scene_item.image_capture())
        assert text_comparer.has_line('NO DATA')

        time.sleep(10)
        assert camera_2_scene_item.image_capture().is_similar_to(SavedImage(gui_prerequisite_store.fetch('test56719/playback.png')))
        text_comparer2 = ImageTextRecognition(camera_1_scene_item.image_capture())
        assert text_comparer2.has_line('NO DATA')


if __name__ == '__main__':
    exit(test_export_bookmarks_different_periods().main())
