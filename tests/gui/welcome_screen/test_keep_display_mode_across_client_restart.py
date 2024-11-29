# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_keep_display_mode_across_client_restart(VMSTest):
    """Welcome screen keep display mode across client restarts.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/79671

    Selection-Tag: 79671
    Selection-Tag: welcome_screen
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        client_installation = exit_stack.enter_context(machine_pool.create_and_setup_only_client())
        client_installation.add_fake_welcome_screen_tiles(5)
        client_installation.set_ini('nx_vms_client_core.ini', {'systemsHideOptions': '8'})
        testkit_api_1 = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid_1 = HID(testkit_api_1)
        welcome_screen_1 = WelcomeScreen(testkit_api_1, hid_1)
        assert welcome_screen_1.get_display_mode() in ('All Systems', 'All Sites')
        welcome_screen_1.get_tile_by_system_name('SQUISH_FAKE0').choose_dropdown_menu_option('Add to Favorites')
        welcome_screen_1.get_tile_by_system_name('SQUISH_FAKE1').choose_dropdown_menu_option('Hide')

        welcome_screen_1.set_display_mode('Favorites')
        client_installation.kill_client_process()
        testkit_api_2 = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid_2 = HID(testkit_api_2)
        welcome_screen_2 = WelcomeScreen(testkit_api_2, hid_2)
        assert welcome_screen_2.get_display_mode() == 'Favorites'
        assert welcome_screen_2.get_tile_count() == 1
        assert welcome_screen_2.get_row_count() == 1
        assert not welcome_screen_2.has_scrollbar()
        assert welcome_screen_2.tile_exists('SQUISH_FAKE0')
        assert welcome_screen_2.get_tile_by_system_name('SQUISH_FAKE0').is_favorite()

        welcome_screen_2.set_display_mode('Hidden')
        client_installation.kill_client_process()
        testkit_api_3 = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid_3 = HID(testkit_api_3)
        welcome_screen_3 = WelcomeScreen(testkit_api_3, hid_3)
        assert welcome_screen_3.get_display_mode() == 'Hidden'
        assert welcome_screen_3.get_tile_count() == 1
        assert welcome_screen_3.get_row_count() == 1
        assert not welcome_screen_3.has_scrollbar()
        assert welcome_screen_3.tile_exists('SQUISH_FAKE1')
        assert welcome_screen_3.get_tile_by_system_name('SQUISH_FAKE1').is_hidden()


if __name__ == '__main__':
    exit(test_keep_display_mode_across_client_restart().main())
