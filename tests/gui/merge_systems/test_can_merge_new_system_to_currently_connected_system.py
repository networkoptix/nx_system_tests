# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re

from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.dialogs.merge_systems import MergeSystemsDialog
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.gui_test_stand import GuiTestStand
from gui.server_login_steps import _log_in_to_server
from gui.server_login_steps import _log_in_using_main_menu
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest

_logger = logging.getLogger(__name__)


class test_can_merge_new_system_to_currently_connected_system(VMSTest):
    """Can merge new system to currently connected system.

    Install server and do not setup it. Connect to another existing system.
    Merge new system into to current one. Disconnect from system and connect to a new system
    using "Connect to another server" dialog with local admin's password.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/6721

    Selection-Tag: 6721
    Selection-Tag: merge_systems
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, server_vm2, client_installation] = exit_stack.enter_context(machine_pool.setup_two_servers_client())
        server_vm.api.restore_state()
        testkit_api = start_desktop_client(machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        address_port_2 = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm2)
        _log_in_to_server(testkit_api, hid, address_port_2, server_vm2)
        our_password = server_vm2.api.get_credentials().password
        their_username = server_vm.api.get_credentials().username
        address, port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        MainMenu(testkit_api, hid).activate_merge_systems()
        MergeSystemsDialog(testkit_api, hid).merge_with_new_server(
            our_password,
            their_username,  # Must be 'admin'
            'admin',
            port,
            address,
            )
        ResourceTree(testkit_api, hid).wait_for_server_count(2)
        servers = server_vm2.api.list_servers()
        server_vm_name = server_vm.api.get_server_name()
        server_vm2_name = server_vm2.api.get_server_name()
        rtree = ResourceTree(testkit_api, hid)
        assert len(servers) == 2
        assert rtree.has_server(server_vm_name)
        assert rtree.has_server(server_vm2_name)

        MainMenu(testkit_api, hid).disconnect_from_server()
        assert not WelcomeScreen(testkit_api, hid).tile_exists(re.compile('New (System|Site)'))

        # In this step we connect to the server using local admin's password
        address_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        _log_in_using_main_menu(testkit_api, hid, address_port, 'admin', our_password)
        rtree = ResourceTree(testkit_api, hid)
        assert len(servers) == 2
        assert rtree.has_server(server_vm_name)
        assert rtree.has_server(server_vm2_name)


if __name__ == '__main__':
    exit(test_can_merge_new_system_to_currently_connected_system().main())
