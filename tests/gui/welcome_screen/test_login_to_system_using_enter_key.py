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


class test_login_to_system_using_enter_key(VMSTest):
    """Login to system by Enter key.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/79736

    Selection-Tag: 79736
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
        MainMenu(testkit_api, hid).disconnect_from_server()
        welcome_screen = WelcomeScreen(testkit_api, hid)
        welcome_screen.get_tile_by_system_name(server_vm.api.get_system_name()).open()
        first_time_connect(testkit_api, hid)
        user = server_vm.api.get_credentials().username
        password = server_vm.api.get_credentials().password
        address, port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        welcome_screen.get_open_tile().set(
            address=f'{address}:{port}',
            user=user,
            password=password,
            )
        hid.keyboard_hotkeys('Enter')
        ResourceTree(testkit_api, hid).get_server(server_vm.api.get_server_name())


if __name__ == '__main__':
    exit(test_login_to_system_using_enter_key().main())
