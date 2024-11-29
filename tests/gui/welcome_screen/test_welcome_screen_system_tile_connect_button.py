# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.dialogs.connect_to_server import first_time_connect
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_welcome_screen_system_tile_connect_button(VMSTest):
    """Welcome screen system tile connect button.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78220

    Selection-Tag: 78220
    Selection-Tag: welcome_screen
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_LOCAL, client_installation] = exit_stack.enter_context(machine_pool.setup_local_bundle_system())
        client_installation.set_ini('nx_vms_client_core.ini', {'systemsHideOptions': '8'})
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        system_name = server_LOCAL.api.get_system_name()
        hid = HID(testkit_api)
        welcome_screen = WelcomeScreen(testkit_api, hid)
        welcome_screen.wait_for_tile_appear(system_name, 20)
        welcome_screen.get_tile_by_system_name(system_name)
        first_time_connect(testkit_api, hid)
        user = server_LOCAL.api.get_credentials().username
        password = server_LOCAL.api.get_credentials().password
        welcome_screen.wait_for_tile_appear(system_name, 20)
        welcome_screen.get_tile_by_system_name(system_name).open()
        open_tile = welcome_screen.get_open_tile()
        address, port = machine_pool.get_address_and_port_of_server_from_bundle_for_client(server_LOCAL)
        open_tile.set(
            address=f'{address}:{port}',
            user=user,
            password=password,
            )
        open_tile.get_connect_button().wait_for_accessible()

        open_tile.get_address_combobox().set_text('')
        open_tile.get_user_combobox().set_text(user)
        open_tile.get_password_qline().type_text(password)
        open_tile.get_connect_button().wait_for_inaccessible()

        open_tile.get_address_combobox().set_text(f'{address}:{port}')
        open_tile.get_user_combobox().set_text('')
        open_tile.get_password_qline().type_text(password)
        open_tile.get_connect_button().wait_for_inaccessible()

        open_tile.get_address_combobox().set_text(f'{address}:{port}')
        open_tile.get_user_combobox().set_text(user)
        open_tile.get_password_qline().type_text('')
        open_tile.get_connect_button().wait_for_inaccessible()


if __name__ == '__main__':
    exit(test_welcome_screen_system_tile_connect_button().main())
