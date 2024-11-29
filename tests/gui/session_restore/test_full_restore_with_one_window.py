# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.left_panel_widget import LeftPanelWidget
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.main_window import MainWindow
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_full_restore_with_one_window(VMSTest):
    """Full Restore with one window.

    #  https://networkoptix.testrail.net/index.php?/cases/view/79097

    Selection-Tag: 79097
    Selection-Tag: session_restore
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        testkit_api, camera_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        left_panel_widget = LeftPanelWidget(testkit_api, hid)
        layout_tab_bar = LayoutTabBar(testkit_api, hid)
        layout_tab_bar.save_current_as('test_layout')
        main_window = MainWindow(testkit_api, hid)
        main_window.put_in_window_mode()
        main_menu = MainMenu(testkit_api, hid)
        main_menu.activate_save_window_configuration()

        layout_tab_bar.close('test_layout')
        main_window.put_in_fullscreen_mode()
        left_panel_widget.hide()
        main_menu.activate_items('Windows Configuration', 'Restore Saved State')

        main_window.wait_for_screen_mode(fullscreen=False)
        assert layout_tab_bar.is_open('test_layout')
        camera_scene_item.wait_for_accessible()
        assert left_panel_widget.is_shown()


if __name__ == '__main__':
    exit(test_full_restore_with_one_window().main())
