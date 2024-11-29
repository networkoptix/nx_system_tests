# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.server_login_steps import _log_in_using_main_menu
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_watermark_screenshots(VMSTest):
    """Watermark on screenshots.

    # https://networkoptix.testrail.net/index.php?/cases/view/42984

    Selection-Tag: 42984
    Selection-Tag: watermarks_playback
    Selection-Tag: screenshots
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
        MainMenu(testkit_api, hid).activate_system_administration().enable_watermark()
        server_vm.api.add_local_advanced_viewer('AV', 'WellKnownPassword2')
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        address_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        _log_in_using_main_menu(testkit_api, hid, address_port, 'AV', 'WellKnownPassword2')
        camera_scene_item = ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open()
        save_screenshot_dialog = camera_scene_item.open_save_screenshot_dialog()
        save_screenshot_dialog.make_screenshot(
            client_installation.temp_dir() / 'watermark',
            'PNG Image (*.png)',
            timestamp='No timestamp',
            camera_name='No camera name',
            )
        ResourceTree(testkit_api, hid).get_local_file('watermark.png').open_in_new_tab()
        loaded = SavedImage(gui_prerequisite_store.fetch('test42984/watermark_testcamera.png'))
        Scene(testkit_api, hid).wait_until_first_item_is_similar_to(loaded)


if __name__ == '__main__':
    exit(test_watermark_screenshots().main())
