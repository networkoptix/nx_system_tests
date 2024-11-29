# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_removing_group_with_devices_from_defferent_servers(VMSTest):
    """Removing group with devices from different servers and resource tree state without servers.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84554

    Selection-Tag: 84554
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
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4'))
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm2.os_access, 'samples/time_test_video.mp4'))
        server_vm_name = server_vm.api.get_server_name()
        server_vm2_name = server_vm2.api.get_server_name()
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        [test_camera_2] = server_vm2.api.add_test_cameras(2, 1)
        ResourceTree(testkit_api, hid).wait_for_cameras([test_camera_1.name, test_camera_2.name])
        ResourceTree(testkit_api, hid).select_cameras([test_camera_1.name]).create_group()
        assert ResourceTree(testkit_api, hid).get_server(server_vm_name).get_group('New Group').has_camera(test_camera_1.name)
        ResourceTree(testkit_api, hid).select_cameras([test_camera_2.name]).create_group()
        assert ResourceTree(testkit_api, hid).get_server(server_vm2_name).get_group('New Group 1').has_camera(test_camera_2.name)

        ResourceTree(testkit_api, hid).get_group('New Group 1').rename_using_context_menu('New Group')
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.get_server(server_vm_name).has_group('New Group')
        assert rtree.get_server(server_vm2_name).has_group('New Group')
        rtree.hide_servers()
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_all_resources_node()
        assert rtree.get_group('New Group').has_camera(test_camera_1.name)
        assert rtree.get_group('New Group').has_camera(test_camera_2.name)
        rtree.select_groups(['New Group']).remove()
        ResourceTree(testkit_api, hid).show_servers()
        rtree = ResourceTree(testkit_api, hid)
        assert not rtree.has_all_resources_node()
        assert not rtree.get_server(server_vm_name).has_group('New Group')
        assert not rtree.get_server(server_vm2_name).has_group('New Group')
        assert rtree.get_server(server_vm_name).has_camera(test_camera_1.name)
        assert rtree.get_server(server_vm2_name).has_camera(test_camera_2.name)


if __name__ == '__main__':
    exit(test_removing_group_with_devices_from_defferent_servers().main())
