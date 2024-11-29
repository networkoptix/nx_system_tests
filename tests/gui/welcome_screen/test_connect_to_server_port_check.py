# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.connect_to_server import first_time_connect
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_connect_to_server_port_check(VMSTest):
    """Welcome screen connecting with wrong port.

    According to test definition server should have a non-default port. Virtual machine servers have
    non-default ports and no additional configuration is needed.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/79673

    Selection-Tag: 79673
    Selection-Tag: welcome_screen
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        client_installation.set_ini('nx_vms_client_core.ini', {'systemsHideOptions': '4'})
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        system_name = server_vm.api.get_system_name()
        MainMenu(testkit_api, hid).disconnect_from_server()
        welcome_screen = WelcomeScreen(testkit_api, hid)
        welcome_screen.wait_for_tile_appear(system_name, 20)
        welcome_screen.get_tile_by_system_name(system_name).open()
        first_time_connect(testkit_api, hid)
        open_tile = welcome_screen.get_open_tile()
        address, _port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        open_tile.get_address_combobox().set_text(f'{address}:1111')
        open_tile.get_user_combobox().set_text(server_vm.api.get_credentials().username)
        open_tile.get_password_qline().type_text(server_vm.api.get_credentials().password)
        open_tile.get_remember_password_checkbox().set(True)
        hid.mouse_left_click_on_object(open_tile.get_connect_button())
        assert 'Internal error. Please try again later.' == open_tile.get_connection_error_message()
        user = server_vm.api.get_credentials().username
        password = server_vm.api.get_credentials().password
        address, port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        open_tile.set(
            address=f'{address}:{port}',
            user=user,
            password=password,
            )
        hid.mouse_left_click_on_object(open_tile.get_connect_button())
        assert ResourceTree(testkit_api, hid).has_server(server_vm.api.get_server_name())


if __name__ == '__main__':
    exit(test_connect_to_server_port_check().main())
