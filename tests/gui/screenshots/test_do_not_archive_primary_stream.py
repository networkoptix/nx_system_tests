# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_do_not_archive_primary_stream(VMSTest):
    """Do not archive primary stream.

    Screenshot saved in low quality

    2. open camera with two streams, record archive, screenshot saved in high quality
    both for low and high camera resolution
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1657

    Selection-Tag: 1657
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
        testkit_api, camera_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        server_vm.api.start_recording(test_camera_1.id)
        time.sleep(60)
        server_vm.api.stop_recording(test_camera_1.id)
        TimelineNavigation(testkit_api, hid).pause_and_to_begin()
        camera_scene_item.open_context_menu().set_resolution('Low')
        save_screenshot_dialog_1 = camera_scene_item.open_save_screenshot_dialog()
        save_screenshot_dialog_1.make_screenshot(
            client_installation.temp_dir() / 'low_quality',
            'PNG Image (*.png)',
            timestamp='No timestamp',
            camera_name='No camera name',
            )
        low_scene_item = ResourceTree(testkit_api, hid).get_local_file('low_quality.png').open_in_new_tab()
        low_scene_item.wait_for_accessible()
        scene = Scene(testkit_api, hid)
        loaded = SavedImage(gui_prerequisite_store.fetch('test1657/low_quality.png'))
        scene.wait_until_first_item_is_similar_to(loaded)
        assert '1332x850' in low_scene_item.get_information()

        LayoutTabBar(testkit_api, hid).close_current_layout()
        camera_scene_item.open_context_menu().set_resolution('High')
        save_screenshot_dialog_2 = camera_scene_item.open_save_screenshot_dialog()
        save_screenshot_dialog_2.make_screenshot(
            client_installation.temp_dir() / 'high_quality',
            'PNG Image (*.png)',
            timestamp='No timestamp',
            camera_name='No camera name',
            )
        high_scene_item = ResourceTree(testkit_api, hid).get_local_file('high_quality.png').open_in_new_tab()
        high_scene_item.wait_for_accessible()
        loaded1 = SavedImage(gui_prerequisite_store.fetch('test1657/high_quality.png'))
        scene.wait_until_first_item_is_similar_to(loaded1)
        assert '1332x850' in high_scene_item.get_information()


if __name__ == '__main__':
    exit(test_do_not_archive_primary_stream().main())
