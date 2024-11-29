# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_moving_group_between_servers(VMSTest):
    """Moving groups between servers If at least one resource can not be moved between servers.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84571
    # This test is unstable due to an issue https://networkoptix.atlassian.net/browse/VMS-47626

    Selection-Tag: 84571
    Selection-Tag: resources_grouping
    Selection-Tag: unstable
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
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        server_vm.api.add_virtual_camera('TestVirtualCamera')
        ResourceTree(testkit_api, hid).wait_for_cameras(['TestVirtualCamera', test_camera_1.name])

        ResourceTree(testkit_api, hid).select_cameras([test_camera_1.name, 'TestVirtualCamera']).create_group()
        assert ResourceTree(testkit_api, hid).get_group('New Group').has_camera(test_camera_1.name)
        assert ResourceTree(testkit_api, hid).get_group('New Group').has_camera('TestVirtualCamera')
        server_vm_name = server_vm.api.get_server_name()
        server_vm2_name = server_vm2.api.get_server_name()
        rtree = ResourceTree(testkit_api, hid)
        rtree.get_group('New Group').drag_n_drop(rtree.get_server(server_vm2_name))
        message_dialog_1 = MessageBox(testkit_api, hid)
        title_1 = message_dialog_1.wait_until_appears(20).get_title()
        assert title_1 == f'Only some of the selected devices can be moved to {server_vm2_name}'
        message_dialog_1.close_by_button('Cancel')
        assert ResourceTree(testkit_api, hid).get_server(server_vm_name).get_group('New Group').has_camera(test_camera_1.name)
        assert ResourceTree(testkit_api, hid).get_server(server_vm_name).get_group('New Group').has_camera('TestVirtualCamera')

        rtree1 = ResourceTree(testkit_api, hid)
        rtree1.get_group('New Group').drag_n_drop(rtree1.get_server(server_vm2_name))
        message_dialog_2 = MessageBox(testkit_api, hid)
        title_2 = message_dialog_2.wait_until_appears(20).get_title()
        assert title_2 == f'Only some of the selected devices can be moved to {server_vm2_name}'
        message_dialog_2.close_by_button('Move Partially', wait_close=False)
        MessageBox(testkit_api, hid).close_by_button('Move')
        assert ResourceTree(testkit_api, hid).get_server(server_vm2_name).get_group('New Group').has_camera(test_camera_1.name)
        assert ResourceTree(testkit_api, hid).get_server(server_vm_name).get_group('New Group').has_camera('TestVirtualCamera')


if __name__ == '__main__':
    exit(test_moving_group_between_servers().main())
