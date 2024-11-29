# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.main_window import MainWindow
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_low_quality_rotated_screenshots(VMSTest):
    """Item rotation and Take screenshot for low quality.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1738

    Selection-Tag: 1738
    Selection-Tag: screenshots
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(
            playing_testcamera(
                machine_pool,
                server_vm.os_access,
                primary_prerequisite='samples/overlay_test_video.mp4',
                secondary_prerequisite='samples/overlay_test_video_lowres.mp4',
                ),
            )
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        testkit_api, camera_scene_item_1 = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        server_vm.api.start_recording(test_camera_1.id)
        time.sleep(60)
        server_vm.api.stop_recording(test_camera_1.id)
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause_and_to_begin()
        camera_scene_item_1.open_context_menu().set_resolution('Low')
        camera_scene_item_1.rotate(50)
        save_screenshot_dialog_1 = camera_scene_item_1.open_save_screenshot_dialog()
        save_screenshot_dialog_1.make_screenshot(
            client_installation.temp_dir() / 'item_rotation_50',
            'PNG Image (*.png)',
            timestamp='Bottom right corner',
            camera_name='Bottom left corner',
            )
        ResourceTree(testkit_api, hid).get_local_file('item_rotation_50.png').open_in_new_tab().wait_for_accessible()
        main_window = MainWindow(testkit_api, hid)
        main_window.hover_away()
        scene = Scene(testkit_api, hid)
        loaded = SavedImage(gui_prerequisite_store.fetch('test1738/expected_50.png'))
        scene.wait_until_first_item_is_similar_to(loaded)

        layout_tab_bar = LayoutTabBar(testkit_api, hid)
        layout_tab_bar.close_current_layout()
        with ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open_settings() as camera_settings:
            camera_settings.general_tab.set_image_rotation(180)
        layout_tab_bar.close_current_layout()
        camera_scene_item_2 = ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open()
        timeline_navigation.pause_and_to_begin()
        camera_scene_item_2.open_context_menu().set_resolution('Low')
        save_screenshot_dialog_2 = camera_scene_item_2.open_save_screenshot_dialog()
        save_screenshot_dialog_2.make_screenshot(
            client_installation.temp_dir() / 'camera_rotation_180',
            'JPEG Image (*.jpg *.jpeg)',
            timestamp='Bottom left corner',
            camera_name='Bottom right corner',
            )
        ResourceTree(testkit_api, hid).get_local_file('camera_rotation_180.jpeg').open_in_new_tab().wait_for_accessible()
        main_window.hover_away()
        loaded1 = SavedImage(gui_prerequisite_store.fetch('test1738/expected_180.png'))
        scene.wait_until_first_item_is_similar_to(loaded1)


if __name__ == '__main__':
    exit(test_low_quality_rotated_screenshots().main())
