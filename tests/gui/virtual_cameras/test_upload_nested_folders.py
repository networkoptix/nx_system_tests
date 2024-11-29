# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from datetime import datetime
from datetime import timedelta

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.camera_settings import CameraSettingsDialog
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineNavigation
from gui.desktop_ui.timeline import TimelineTooltip
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_upload_nested_folders(VMSTest):
    """Upload nested folders.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/41524
    # Comparison images need to be changed after fixing VMS-15180

    Selection-Tag: xfail
    Selection-Tag: 41524
    Selection-Tag: virtual_cameras
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        new_virtual_camera = MainMenu(testkit_api, hid).activate_new_virtual_camera()
        new_virtual_camera.add_virtual_camera('VirtualCamera')
        with CameraSettingsDialog(testkit_api, hid) as camera_settings:
            camera_settings.general_tab.set_auto_min_keep_archive(True)
            camera_settings.general_tab.set_auto_max_keep_archive(True)
        camera_node = ResourceTree(testkit_api, hid).get_camera('VirtualCamera')
        upload_dialog = camera_node.open_upload_folder_dialog()
        avi_path = gui_prerequisite_supplier.upload_to_remote('upload/Nested_folders/avi.avi', client_installation.os_access)
        gui_prerequisite_supplier.upload_to_remote('upload/Nested_folders/Level1/mkv.mkv', client_installation.os_access)
        gui_prerequisite_supplier.upload_to_remote('upload/Nested_folders/Level1/Level2/mov.mov', client_installation.os_access)
        gui_prerequisite_supplier.upload_to_remote(
            'upload/Nested_folders/Level1/Level2/Level3/overlapped_timestamps_1.mkv', client_installation.os_access)
        file_path = avi_path.parent
        upload_dialog.multi_upload_files([file_path], 50)
        camera_node.open_in_new_tab()
        scene = Scene(testkit_api, hid)
        scene.wait_for_items_number(1)
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause_and_to_begin()
        time.sleep(2)
        timeline_tooltip = TimelineTooltip(testkit_api)
        timeline_tooltip.verify_datetime(
            datetime.fromisoformat('2017-11-29T23:36:54'),
            tolerance=(timedelta(seconds=0)),
            )
        loaded_one = SavedImage(gui_prerequisite_store.fetch('comparison/vc_screen.png'))
        scene.wait_until_first_item_is_similar_to(loaded_one)
        assert abs(_get_timeline_chunk_duration(testkit_api, hid) - timedelta(seconds=17)) < timedelta(seconds=2)
        timeline_navigation.to_end()
        time.sleep(2)
        timeline_tooltip.verify_datetime(
            datetime.fromisoformat('2018-06-04T15:52:59'),
            tolerance=(timedelta(seconds=0)),
            )
        loaded_two = SavedImage(gui_prerequisite_store.fetch('comparison/vc_screen2.png'))
        scene.wait_until_first_item_is_similar_to(loaded_two)
        assert abs(_get_timeline_chunk_duration(testkit_api, hid) - timedelta(minutes=1)) < timedelta(seconds=2)
        timeline_navigation.to_end()
        time.sleep(2)
        timeline_tooltip.verify_datetime(
            datetime.fromisoformat('2018-06-05T18:57:07'),
            tolerance=(timedelta(seconds=0)),
            )
        loaded_three = SavedImage(gui_prerequisite_store.fetch('comparison/vc_screen3.png'))
        scene.wait_until_first_item_is_similar_to(loaded_three)
        assert abs(_get_timeline_chunk_duration(testkit_api, hid) - timedelta(seconds=20)) < timedelta(seconds=2)
        timeline_navigation.to_end()
        time.sleep(2)
        timeline_tooltip.verify_datetime(
            datetime.fromisoformat('2018-06-28T19:05:54'),
            tolerance=(timedelta(seconds=0)),
            )
        loaded_four = SavedImage(gui_prerequisite_store.fetch('comparison/vc_screen4.png'))
        scene.wait_until_first_item_is_similar_to(loaded_four)
        assert abs(_get_timeline_last_chunk_duration(testkit_api, hid) - timedelta(minutes=1, seconds=14)) < timedelta(seconds=2)


def _get_timeline_chunk_duration(testkit_api, hid):
    start_chunk = TimelineTooltip(testkit_api).date_time()
    preview_tooltip = Timeline(testkit_api, hid).show_chunk_preview_tooltip()
    end_chunk = preview_tooltip.get_date_time()
    actual_length = end_chunk - start_chunk
    return actual_length


def _get_timeline_last_chunk_duration(testkit_api, hid):
    start_chunk = TimelineTooltip(testkit_api).date_time()
    TimelineNavigation(testkit_api, hid).to_end()
    time.sleep(2)
    end_chunk = TimelineTooltip(testkit_api).date_time()
    actual_length = end_chunk - start_chunk
    return actual_length


if __name__ == '__main__':
    exit(test_upload_nested_folders().main())
