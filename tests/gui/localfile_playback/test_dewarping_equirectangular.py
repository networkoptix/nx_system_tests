# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.main_window import MainWindow
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_dewarping_equirectangular(VMSTest):
    """Application to camera for video from archive.

    Set dewarping equirectangular mode in camera settings,
    check horizontal correction options appear, check preview looks like expected,
    open camera at the scene, check dewarping mode is enabled, check items look like expected,
    disable dewarping for the item, check item is changed, dewarping mode is off,
    then enable dewarping for the item, check dewarping mode is on, the item looks dewarped.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78241

    Selection-Tag: 78241
    Selection-Tag: localfile_playback
    Selection-Tag: dewarping
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/dewarped_static_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        testkit_api, camera_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        with ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open_settings() as camera_settings:
            camera_settings.activate_tab('Dewarping')
            assert not camera_settings.dewarping_tab.get_dewarping_checkbox_state()

            camera_settings.dewarping_tab.enable_dewarping()
            camera_settings.dewarping_tab.set_equirectangular_dewarping_mode()
            assert camera_settings.dewarping_tab.are_horizontal_options_accessible()
            # TODO: Add correct reference picture for dewarped preview.
            path = gui_prerequisite_store.fetch('test78241/dewarped_preview.png')
            preview = camera_settings.dewarping_tab.get_dewarping_preview_equirectangular()
            assert preview.is_similar_to(SavedImage(path))

        assert camera_scene_item.button_checked('Dewarping')

        main_window = MainWindow(testkit_api, hid)
        main_window.hover_away()
        loaded_dewarped_scene = SavedImage(gui_prerequisite_store.fetch('test78241/dewarped_scene.png'))
        scene = Scene(testkit_api, hid)
        scene.wait_until_first_item_is_similar_to(loaded_dewarped_scene)

        camera_scene_item.deactivate_button('Dewarping')
        assert not camera_scene_item.button_checked('Dewarping')

        main_window.hover_away()
        loaded_not_dewarped_scene = SavedImage(gui_prerequisite_store.fetch('test78241/not_dewarped_scene.png'))
        scene.wait_until_first_item_is_similar_to(loaded_not_dewarped_scene)

        camera_scene_item.activate_button('Dewarping')
        assert camera_scene_item.button_checked('Dewarping')

        main_window.hover_away()
        time.sleep(1)
        scene.wait_until_first_item_is_similar_to(loaded_dewarped_scene)


if __name__ == '__main__':
    exit(test_dewarping_equirectangular().main())
