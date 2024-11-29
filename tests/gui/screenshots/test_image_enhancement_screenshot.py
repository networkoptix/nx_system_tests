# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.dialogs.image_enhancement import ImageEnhancementDialog
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_image_enhancement_screenshot(VMSTest):
    """Image enhancement and Take screenshot.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1659

    Selection-Tag: 1659
    Selection-Tag: screenshots
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        testkit_api, camera_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        # VMS-35984: The ticket was moved to Future.
        # The current behavior is considered to be correct.
        # Keyboard shortcuts work only after scene item click
        camera_scene_item.click()
        hid.keyboard_hotkeys('Alt', 'J')
        with ImageEnhancementDialog(testkit_api, hid) as image_enhancement_dialog:
            image_enhancement_dialog.set_image_enhancement(True)
            image_enhancement_dialog.set_gamma(1.0)
            image_enhancement_dialog.set_black_level(50.0)
            image_enhancement_dialog.set_white_level(50.0)
        save_screenshot_dialog = camera_scene_item.open_save_screenshot_dialog()
        save_screenshot_dialog.make_screenshot(
            client_installation.temp_dir() / 'enhancement',
            'PNG Image (*.png)',
            timestamp='No timestamp',
            camera_name='No camera name',
            )
        ResourceTree(testkit_api, hid).get_local_file('enhancement.png').open_in_new_tab().wait_for_accessible()
        loaded = SavedImage(gui_prerequisite_store.fetch('test1659/enhancement.png'))
        Scene(testkit_api, hid).wait_until_first_item_is_similar_to(loaded)


if __name__ == '__main__':
    exit(test_image_enhancement_screenshot().main())
