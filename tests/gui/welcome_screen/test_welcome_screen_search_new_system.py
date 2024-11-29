# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re

from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_welcome_screen_search_new_system(VMSTest):
    """Welcome screen search new system.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/79730

    Selection-Tag: 79730
    Selection-Tag: welcome_screen
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        server_LOCAL, client_installation = exit_stack.enter_context(machine_pool.setup_uninitialized_local_bundle_system())
        client_installation.add_fake_welcome_screen_tiles(5)
        client_installation.set_ini('nx_vms_client_core.ini', {'systemsHideOptions': '8'})
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        welcome_screen = WelcomeScreen(testkit_api, hid)
        welcome_screen.wait_for_tile_appear(re.compile('New (System|Site)'), 3)
        welcome_screen.search('New S')
        welcome_screen.wait_for_tile_appear(re.compile('New (System|Site)'), 3)


if __name__ == '__main__':
    exit(test_welcome_screen_search_new_system().main())
