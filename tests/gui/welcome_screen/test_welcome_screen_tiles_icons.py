# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re

from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.dialogs.connect_to_server import first_time_connect
from gui.desktop_ui.dialogs.system_setup import SystemSetupDialog
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_welcome_screen_tiles_icons(VMSTest):
    """Welcome screen tiles icons.

    The test checks if tiles have correct icons. We already use icons to validate that
    tile is hidden, favorite or else.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78217

    Selection-Tag: 78217
    Selection-Tag: welcome_screen
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        server_LOCAL, client_installation = exit_stack.enter_context(machine_pool.setup_uninitialized_local_bundle_system())
        client_installation.set_ini('nx_vms_client_core.ini', {'systemsHideOptions': '8'})
        client_installation.set_ini('desktop_client.ini', {'simpleModeTilesNumber': '1'})
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        welcome_screen = WelcomeScreen(testkit_api, hid)
        assert welcome_screen.get_cloud_tile().has_correct_icon()
        assert welcome_screen.get_connect_tile().has_correct_icon()
        welcome_screen.wait_for_tile_appear('New (System|Site)', 10)
        tile = welcome_screen.get_tile_by_system_name(re.compile('New (System|Site)'))
        assert tile.has_gear_icon()
        tile.click()
        first_time_connect(testkit_api, hid)

        SystemSetupDialog(testkit_api, hid).setup(title='Test system', password='WellKnownPassword2')
        # Wait until connection to the new system performs.
        ResourceTree(testkit_api, hid).wait_for_current_user()
        server_LOCAL.api.set_credentials('admin', 'WellKnownPassword2')
        MainMenu(testkit_api, hid).disconnect_from_server()
        welcome_screen.get_tile_by_system_name('Test system').choose_dropdown_menu_option('Add to Favorites')
        assert welcome_screen.tile_exists('Test system')
        assert welcome_screen.get_tile_by_system_name('Test system').is_favorite()

        welcome_screen.get_tile_by_system_name('Test system').choose_dropdown_menu_option('Hide')
        welcome_screen.set_display_mode('Hidden')
        assert welcome_screen.tile_exists('Test system')
        assert welcome_screen.get_tile_by_system_name('Test system').is_hidden()


if __name__ == '__main__':
    exit(test_welcome_screen_tiles_icons().main())
