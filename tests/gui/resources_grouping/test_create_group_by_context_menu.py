# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_create_group_by_context_menu(VMSTest):
    """Create group by context menu.

    Login as an administrator. Create groups by context menu.
    Check: New groups creates in editable mode and expanded. Groups have the correct order.

    #  https://networkoptix.testrail.net/index.php?/cases/view/84537

    Selection-Tag: 84537
    Selection-Tag: resources_grouping
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        # same video for multiple cameras
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4', count=3))
        [test_camera_1, test_camera_2, test_camera_3] = server_vm.api.add_test_cameras(0, 3)

        ResourceTree(testkit_api, hid).select_cameras([(test_camera_1.name)]).create_group()
        assert ResourceTree(testkit_api, hid).get_group('New Group').has_camera(test_camera_1.name)

        ResourceTree(testkit_api, hid).select_cameras([(test_camera_1.name)]).create_group()
        assert ResourceTree(testkit_api, hid).get_group('New Group 1').has_camera(test_camera_1.name)
        group = ResourceTree(testkit_api, hid).get_group('New Group')
        for name in ['New Group 1']:
            assert group.has_group(name)

        group_names = ['New Group']
        ResourceTree(testkit_api, hid).select_groups(group_names).create_group()
        group1 = ResourceTree(testkit_api, hid).get_group('New Group 2')
        for name1 in ['New Group']:
            assert group1.has_group(name1)

        ResourceTree(testkit_api, hid).select_cameras([test_camera_3.name, test_camera_2.name]).create_group()
        assert ResourceTree(testkit_api, hid).get_group('New Group 3').has_camera(test_camera_3.name)
        assert ResourceTree(testkit_api, hid).get_group('New Group 3').has_camera(test_camera_2.name)


if __name__ == '__main__':
    exit(test_create_group_by_context_menu().main())
