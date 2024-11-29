# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.dialogs.connect_to_cloud import CloudAuthConnect
from gui.desktop_ui.dialogs.connect_to_server import ConnectToServerDialog
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.gui_test_stand import GuiTestStand
from gui.server_login_steps import _log_in_to_server
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_welcome_screen_hotkeys(VMSTest):
    """Welcome screen hotkeys.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/83954

    Selection-Tag: 83954
    Selection-Tag: welcome_screen
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_LOCAL, client_installation] = exit_stack.enter_context(machine_pool.setup_local_bundle_system())
        client_installation.set_ini('nx_vms_client_core.ini', {'systemsHideOptions': '8'})
        client_installation.add_fake_welcome_screen_tiles(5)
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        system_name = server_LOCAL.api.get_system_name()
        hid = HID(testkit_api)
        address_port = machine_pool.get_address_and_port_of_server_from_bundle_for_client(server_LOCAL)
        _log_in_to_server(testkit_api, hid, address_port, server_LOCAL)
        MainMenu(testkit_api, hid).disconnect_from_server()
        server_LOCAL.stop()

        welcome_screen = WelcomeScreen(testkit_api, hid)
        hid.keyboard_hotkeys('Ctrl', 'F')
        assert welcome_screen.search_is_active()
        hid.keyboard_hotkeys('a')
        assert welcome_screen.get_search_text() == 'a'
        hid.keyboard_hotkeys('b')
        assert welcome_screen.get_search_text() == 'ab'

        welcome_screen.clear_search()
        welcome_screen.click_logo()
        hid.keyboard_hotkeys('Ctrl', 'Shift', 'C')
        ConnectToServerDialog(testkit_api, hid).cancel()
        welcome_screen.wait_for_tile_appear(system_name, 20)
        system_tile = welcome_screen.get_tile_by_system_name(system_name)
        assert not system_tile.is_online()
        assert system_tile.has_dropdown_menu()

        hid.keyboard_hotkeys('Ctrl', 'Shift', 'L')
        cloud_auth_dialog = CloudAuthConnect(testkit_api, hid)
        assert cloud_auth_dialog.is_accessible_timeout(timeout=10)
        time.sleep(1)
        cloud_auth_dialog.close()

        hid.keyboard_press('Shift')
        assert not system_tile.is_online()
        assert system_tile.has_trash_button()
        hid.keyboard_release('Shift')
        system_tile.remove_using_shift()
        welcome_screen.wait_for_tile_disappear(20, system_name)

        server_LOCAL.start()
        welcome_screen.wait_for_tile_appear(system_name, 20)
        system_tile = welcome_screen.get_tile_by_system_name(system_name)
        system_tile.choose_dropdown_menu_option('Add to Favorites')
        hid.keyboard_hotkeys('Alt', 'F')
        assert welcome_screen.get_display_mode() == 'Favorites'
        assert welcome_screen.tile_exists(system_name)
        assert system_tile.is_favorite()

        system_tile.choose_dropdown_menu_option('Hide')
        hid.keyboard_hotkeys('Alt', 'H')
        system_tile = welcome_screen.get_tile_by_system_name(system_name)
        assert welcome_screen.get_display_mode() == 'Hidden'
        assert welcome_screen.tile_exists(system_name)
        assert system_tile.is_hidden()

        system_tile.choose_dropdown_menu_option('Show')
        hid.keyboard_hotkeys('Alt', 'A')
        assert welcome_screen.get_display_mode() in ('All Systems', 'All Sites')
        assert welcome_screen.tile_exists(system_name)
        system_tile = welcome_screen.get_tile_by_system_name(system_name)
        assert not system_tile.is_favorite()
        assert not system_tile.is_hidden()


if __name__ == '__main__':
    exit(test_welcome_screen_hotkeys().main())
