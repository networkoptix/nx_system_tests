# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_systems
from tests.base_test import VMSTest


class test_delete_server(VMSTest):
    """Delete only offline servers.

    Stop one server in the system and delete this server, check it has been removed.

    # https://networkoptix.testrail.net/index.php?/cases/view/28

    Selection-Tag: 28
    Selection-Tag: server_configuration
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, server_vm2, client_installation] = exit_stack.enter_context(machine_pool.setup_two_servers_client())
        merge_systems(server_vm, server_vm2, take_remote_settings=False)
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        server_vm2_name = server_vm2.api.get_server_name()
        server_vm2.stop()
        ResourceTree(testkit_api, hid).get_server(server_vm2_name).remove()
        assert not ResourceTree(testkit_api, hid).has_server(server_vm2_name)


if __name__ == '__main__':
    exit(test_delete_server().main())
