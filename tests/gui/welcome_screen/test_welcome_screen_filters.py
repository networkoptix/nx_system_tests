# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re

from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_welcome_screen_filters(VMSTest):
    """Welcome screen filters.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/76629

    Selection-Tag: 76629
    Selection-Tag: welcome_screen
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        client_installation = exit_stack.enter_context(machine_pool.create_and_setup_only_client())
        client_installation.add_fake_welcome_screen_tiles(6)
        client_installation.set_ini('nx_vms_client_core.ini', {'systemsHideOptions': '8'})
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        welcome_screen = WelcomeScreen(testkit_api, hid)
        welcome_screen.get_tile_by_system_name('SQUISH_FAKE0').choose_dropdown_menu_option('Add to Favorites')
        welcome_screen.get_tile_by_system_name('SQUISH_FAKE1').choose_dropdown_menu_option('Add to Favorites')
        welcome_screen.get_tile_by_system_name('SQUISH_FAKE2').choose_dropdown_menu_option('Hide')
        welcome_screen.get_tile_by_system_name('SQUISH_FAKE3').choose_dropdown_menu_option('Hide')

        welcome_screen.set_display_mode('Favorites')
        assert welcome_screen.tile_exists('SQUISH_FAKE0')
        assert welcome_screen.tile_exists('SQUISH_FAKE1')
        assert not welcome_screen.tile_exists('SQUISH_FAKE2')
        assert not welcome_screen.tile_exists('SQUISH_FAKE3')
        assert not welcome_screen.tile_exists('SQUISH_FAKE4')
        assert not welcome_screen.tile_exists('SQUISH_FAKE5')

        welcome_screen.set_display_mode('Hidden')
        assert not welcome_screen.tile_exists('SQUISH_FAKE0')
        assert not welcome_screen.tile_exists('SQUISH_FAKE1')
        assert welcome_screen.tile_exists('SQUISH_FAKE2')
        assert welcome_screen.tile_exists('SQUISH_FAKE3')
        assert not welcome_screen.tile_exists('SQUISH_FAKE4')
        assert not welcome_screen.tile_exists('SQUISH_FAKE5')

        welcome_screen.set_display_mode(re.compile('All (Systems|Sites)'))
        assert welcome_screen.tile_exists('SQUISH_FAKE0')
        assert welcome_screen.tile_exists('SQUISH_FAKE1')
        assert not welcome_screen.tile_exists('SQUISH_FAKE2')
        assert not welcome_screen.tile_exists('SQUISH_FAKE3')
        assert welcome_screen.tile_exists('SQUISH_FAKE4')
        assert welcome_screen.tile_exists('SQUISH_FAKE5')


if __name__ == '__main__':
    exit(test_welcome_screen_filters().main())
