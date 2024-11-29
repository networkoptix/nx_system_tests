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


class test_welcome_screen_new_system_setup(VMSTest):
    """Welcome screen new system setup without remember password.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78218
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/15732

    Selection-Tag: 78218
    Selection-Tag: 15732
    Selection-Tag: welcome_screen
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        server_LOCAL, client_installation = exit_stack.enter_context(machine_pool.setup_uninitialized_local_bundle_system())
        client_installation.set_ini('desktop_client.ini', {'hideOtherSystemsFromResourceTree': 'true'})
        client_installation.set_ini('nx_vms_client_core.ini', {'systemsHideOptions': '8'})
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        welcome_screen = WelcomeScreen(testkit_api, hid)
        welcome_screen.wait_for_tile_appear('New (System|Site)', 20)
        new_system_tile = welcome_screen.get_tile_by_system_name(re.compile('New (System|Site)'))
        assert new_system_tile.get_subtitle() == 'localhost'
        assert new_system_tile.is_pending()
        assert not new_system_tile.has_dropdown_menu()
        assert new_system_tile.has_gear_icon()
        new_system_tile.click()
        first_time_connect(testkit_api, hid)
        system_setup_dialog = SystemSetupDialog(testkit_api, hid)
        system_name = 'Test system'
        username = 'admin'
        password = 'ArbitraryPassword'
        system_setup_dialog.setup(title=system_name, password=password)
        # Wait until connection to the new system performs.
        ResourceTree(testkit_api, hid).wait_for_current_user()
        server_LOCAL.api.set_credentials(username, password)
        server_name = server_LOCAL.api.get_server_name()
        MainMenu(testkit_api, hid).disconnect_from_server()
        test_system_tile = welcome_screen.get_tile_by_system_name(system_name)
        assert test_system_tile.get_subtitle() == 'localhost'
        assert not test_system_tile.is_pending()
        assert test_system_tile.has_dropdown_menu()
        assert not test_system_tile.has_gear_icon()
        test_system_tile.open()
        open_tile = welcome_screen.get_open_tile()
        address, port = machine_pool.get_address_and_port_of_server_from_bundle_for_client(server_LOCAL)
        open_tile.set(
            address,
            username,
            password,
            False,
            )
        hid.mouse_left_click_on_object(open_tile.get_connect_button())
        assert ResourceTree(testkit_api, hid).has_server(server_name)


if __name__ == '__main__':
    exit(test_welcome_screen_new_system_setup().main())
