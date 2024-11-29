# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.dialogs.connect_to_server import first_time_connect
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_logout_after_automatic_login(VMSTest):
    """Welcome screen has no expanded tile when logged out after automatic login.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/79565

    Selection-Tag: 79565
    Selection-Tag: welcome_screen
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_LOCAL, client_installation] = exit_stack.enter_context(machine_pool.setup_local_bundle_system())
        system_name = server_LOCAL.api.get_system_name()
        client_installation.set_ini('nx_vms_client_core.ini', {'systemsHideOptions': '8'})
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        welcome_screen = WelcomeScreen(testkit_api, hid)
        welcome_screen.wait_for_tile_appear(system_name, 3)
        welcome_screen.get_tile_by_system_name(system_name).open()
        address, _port = machine_pool.get_address_and_port_of_server_from_bundle_for_client(server_LOCAL)
        welcome_screen.get_open_tile().set(
            address,
            server_LOCAL.api.get_credentials().username,
            server_LOCAL.api.get_credentials().password,
            True,
            )
        hid.mouse_left_click_on_object(welcome_screen.get_open_tile().get_connect_button())
        first_time_connect(testkit_api, hid)
        MainMenu(testkit_api, hid).disconnect_from_server()
        assert not welcome_screen.has_open_tile()


if __name__ == '__main__':
    exit(test_logout_after_automatic_login().main())