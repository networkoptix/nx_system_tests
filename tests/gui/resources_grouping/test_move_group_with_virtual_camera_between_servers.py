# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_systems
from tests.base_test import VMSTest


class test_move_group_with_virtual_camera_between_servers(VMSTest):
    """All resources from the group can not be moved between servers.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84632

    Selection-Tag: 84632
    Selection-Tag: resources_grouping
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
        rtree = ResourceTree(testkit_api, hid)
        server_vm.api.add_virtual_camera('TestVirtualCamera')
        rtree.wait_for_camera_on_server(server_vm.api.get_server_name(), 'TestVirtualCamera')
        rtree.select_cameras(['TestVirtualCamera']).create_group()
        rtree.reload()
        assert rtree.get_group('New Group').has_camera('TestVirtualCamera')
        rtree.get_group('New Group').drag_n_drop(rtree.get_server(server_vm2.api.get_server_name()))
        message_dialog = MessageBox(testkit_api, hid)
        assert message_dialog.wait_until_appears(20).get_title() == 'Virtual cameras cannot be moved between servers'
        message_dialog.close_by_button('OK')
        rtree.reload()
        assert rtree.get_server(server_vm.api.get_server_name()).has_group('New Group')
        assert not rtree.get_server(server_vm2.api.get_server_name()).has_group('New Group')


if __name__ == '__main__':
    exit(test_move_group_with_virtual_camera_between_servers().main())
