# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import extract_start_timestamp
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_image_enhancement_gamma_black_white_balance(VMSTest):
    """Image enhancement gamma and black and white balance.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1873

    Selection-Tag: 1873
    Selection-Tag: scene_items
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        local_file_path = gui_prerequisite_store.fetch('upload/overlapped_timestamps_1.mkv')
        start_time = extract_start_timestamp(local_file_path)
        camera_id = server_vm.api.add_virtual_camera('VirtualCamera')
        with server_vm.api.virtual_camera_locked(camera_id) as token:
            server_vm.api.upload_to_virtual_camera(camera_id, local_file_path, token, start_time)
        testkit_api, camera_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, 'VirtualCamera')
        hid = HID(testkit_api)
        scene = Scene(testkit_api, hid)
        TimelineNavigation(testkit_api, hid).pause_and_to_begin()

        with camera_scene_item.open_context_menu().open_image_enhancement() as image_enhancement_dialog:
            image_enhancement_dialog.set_gamma(0.10)
        loaded_default = SavedImage(gui_prerequisite_store.fetch('test1873/default.png'))
        scene.wait_until_first_item_is_similar_to(loaded_default)

        with camera_scene_item.open_context_menu().open_image_enhancement() as image_enhancement_dialog:
            image_enhancement_dialog.set_image_enhancement(True)
        loaded_gamma = SavedImage(gui_prerequisite_store.fetch('test1873/gamma.png'))
        scene.wait_until_first_item_is_similar_to(loaded_gamma)

        with camera_scene_item.open_context_menu().open_image_enhancement() as image_enhancement_dialog:
            image_enhancement_dialog.set_black_level(99.0)
        loaded_back_max = SavedImage(gui_prerequisite_store.fetch('test1873/black1.png'))
        scene.wait_until_first_item_is_similar_to(loaded_back_max)

        with camera_scene_item.open_context_menu().open_image_enhancement() as image_enhancement_dialog:
            image_enhancement_dialog.set_black_level(0.10)
        loaded_back_min = SavedImage(gui_prerequisite_store.fetch('test1873/black2.png'))
        scene.wait_until_first_item_is_similar_to(loaded_back_min)

        with camera_scene_item.open_context_menu().open_image_enhancement() as image_enhancement_dialog:
            image_enhancement_dialog.set_white_level(99.1)
        loaded_white_max = SavedImage(gui_prerequisite_store.fetch('test1873/white1.png'))
        scene.wait_until_first_item_is_similar_to(loaded_white_max)

        with camera_scene_item.open_context_menu().open_image_enhancement() as image_enhancement_dialog:
            image_enhancement_dialog.set_white_level(0.10)
        loaded_white_min = SavedImage(gui_prerequisite_store.fetch('test1873/white2.png'))
        scene.wait_until_first_item_is_similar_to(loaded_white_min)


if __name__ == '__main__':
    exit(test_image_enhancement_gamma_black_white_balance().main())
