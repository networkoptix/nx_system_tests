# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.dialogs.connect_to_server import first_time_connect
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.gui_test_stand import GuiTestStand
from gui.server_login_steps import _log_in_to_server
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_welcome_screen_save_password(VMSTest):
    """Save password when logging in from welcome screen.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/79568

    Selection-Tag: 79568
    Selection-Tag: welcome_screen
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        client_installation.set_ini('nx_vms_client_core.ini', {'systemsHideOptions': '4'})
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        address_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        _log_in_to_server(testkit_api, hid, address_port, server_vm)
        system_name = server_vm.api.get_system_name()
        server_vm.api.add_local_viewer('User2', 'verylongpassword234')
        server_vm.api.add_local_viewer('User3', 'User3User3User3User3User3')
        main_menu = MainMenu(testkit_api, hid)
        main_menu.disconnect_from_server()
        welcome_screen = WelcomeScreen(testkit_api, hid)
        welcome_screen.wait_for_tile_appear(system_name, 20)
        welcome_screen.get_tile_by_system_name(system_name).open()
        first_time_connect(testkit_api, hid)
        open_tile = welcome_screen.get_open_tile()
        address, port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        open_tile.get_address_combobox().set_text(f'{address}:{port}')
        open_tile.get_user_combobox().set_text(server_vm.api.get_credentials().username)
        open_tile.get_password_qline().type_text(server_vm.api.get_credentials().password)
        open_tile.get_remember_password_checkbox().set(True)
        hid.mouse_left_click_on_object(open_tile.get_connect_button())
        server_name = server_vm.api.get_server_name()
        assert ResourceTree(testkit_api, hid).has_server(server_name)
        main_menu.disconnect_from_server()
        welcome_screen.get_tile_by_system_name(server_vm.api.get_system_name()).open()
        first_time_connect(testkit_api, hid)
        assert ResourceTree(testkit_api, hid).has_server(server_name)
        main_menu.disconnect_from_server()
        welcome_screen.get_tile_by_system_name(server_vm.api.get_system_name()).choose_dropdown_menu_option('Edit')
        open_tile = welcome_screen.get_open_tile()
        address, port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        open_tile.get_address_combobox().set_text(f'{address}:{port}')
        open_tile.get_user_combobox().set_text('User2')
        open_tile.get_password_qline().type_text('verylongpassword234')
        open_tile.get_remember_password_checkbox().set(True)
        hid.mouse_left_click_on_object(open_tile.get_connect_button())
        assert ResourceTree(testkit_api, hid).has_server(server_name)
        main_menu.disconnect_from_server()
        welcome_screen.get_tile_by_system_name(server_vm.api.get_system_name()).open()
        assert ResourceTree(testkit_api, hid).has_server(server_name)
        main_menu.disconnect_from_server()
        welcome_screen.get_tile_by_system_name(server_vm.api.get_system_name()).choose_dropdown_menu_option('Edit')
        open_tile = welcome_screen.get_open_tile()
        address, port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        open_tile.get_address_combobox().set_text(f'{address}:{port}')
        open_tile.get_user_combobox().set_text('User3')
        open_tile.get_password_qline().type_text('User3User3User3User3User3')
        open_tile.get_remember_password_checkbox().set(False)
        hid.mouse_left_click_on_object(open_tile.get_connect_button())
        main_menu.disconnect_from_server()
        welcome_screen.get_tile_by_system_name(server_vm.api.get_system_name()).open()
        assert welcome_screen.has_open_tile()


if __name__ == '__main__':
    exit(test_welcome_screen_save_password().main())
