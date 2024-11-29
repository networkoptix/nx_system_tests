# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.main_window import MainWindow
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.scene_items import SceneItem
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_screenshot_dewarping(VMSTest):
    """Screenshot for local file.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78243

    Selection-Tag: 78243
    Selection-Tag: localfile_playback
    Selection-Tag: dewarping
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
        remote_path = gui_prerequisite_supplier.upload_to_remote('localfiles/dewarped_static_video.mp4', client_installation.os_access)
        main_menu = MainMenu(testkit_api, hid)
        main_menu.open_local_settings_dialog().add_folder(remote_path.parent)
        ResourceTree(testkit_api, hid).wait_for_any_local_file()
        item = ResourceTree(testkit_api, hid).get_local_file('dewarped_static_video.mp4').open()
        with item.open_context_menu().open_file_settings() as file_settings:
            assert not file_settings.is_dewarping_enabled()
            assert not file_settings.are_horizontal_options_accessible()

            file_settings.enable_dewarping()
            file_settings.set_equirectangular_dewarping_mode()
            assert file_settings.are_horizontal_options_accessible()
        assert item.button_checked('Dewarping')
        main_window = MainWindow(testkit_api, hid)
        main_window.hover_away()
        loaded = SavedImage(gui_prerequisite_store.fetch('test78243/dewarped_scene.png'))
        scene = Scene(testkit_api, hid)
        scene.wait_until_first_item_is_similar_to(loaded)

        save_screen_dialog = item.open_save_screenshot_dialog()
        save_screen_dialog.make_screenshot(
            client_installation.temp_dir() / 'screenshot',
            'PNG Image (*.png)',
            timestamp='No timestamp')

        LayoutTabBar(testkit_api, hid).close_current_layout()
        # temporary file opened with menu and may not be available in the list of local files in tree
        main_menu.open_file(client_installation.temp_dir() / 'screenshot.png')
        SceneItem(testkit_api, hid, 'screenshot.png').wait_for_accessible()
        main_window.hover_away()
        loaded = SavedImage(gui_prerequisite_store.fetch('test78243/screenshot.png'))
        scene.wait_until_first_item_is_similar_to(loaded)


if __name__ == '__main__':
    exit(test_screenshot_dewarping().main())
