# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_take_scene_item_screenshot_for_low_quality(VMSTest):
    """Take screenshot for low quality.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1739

    Selection-Tag: 1739
    Selection-Tag: screenshots
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        [test_camera_1] = testcameras_with_just_recorded_archive(nx_server=server_vm, video_file='samples/test_video.mp4')
        testkit_api, camera_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        with ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open_settings() as camera_settings:
            camera_settings.general_tab.set_aspect_ratio('1:1')
        TimelineNavigation(testkit_api, hid).pause_and_to_begin()
        time.sleep(2)
        camera_scene_item.open_context_menu().set_resolution('Low')
        save_screenshot_dialog = camera_scene_item.open_save_screenshot_dialog()
        save_screenshot_dialog.make_screenshot(
            client_installation.temp_dir() / 'screenshot_with_fixed_AR', 'PNG Image (*.png)',
            timestamp='Top right corner',
            camera_name='Top left corner',
            )
        # temporary file opened with menu and may not be available in the list of local files in tree
        MainMenu(testkit_api, hid).open_file(client_installation.temp_dir() / 'screenshot_with_fixed_AR.png')
        scene = Scene(testkit_api, hid)
        scene.wait_for_items_number(2)
        screen = scene.item_image(1)
        loaded = SavedImage(gui_prerequisite_store.fetch('test1739/screen.png'))
        assert screen.is_similar_to(loaded)


if __name__ == '__main__':
    exit(test_take_scene_item_screenshot_for_low_quality().main())
