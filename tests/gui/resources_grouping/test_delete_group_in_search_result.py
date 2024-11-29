# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_delete_group_in_search_result(VMSTest):
    """Delete group in search result.

    Select 2 cameras and create group by context menu.
    Input the group's name in search field. Group is found.
    Remove group and clear search field. Cameras exists in resources tree.

    #  https://networkoptix.testrail.net/index.php?/cases/view/84610

    Selection-Tag: 84610
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
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4', count=2))
        [test_camera_1, test_camera_2] = server_vm.api.add_test_cameras(0, 2)

        ResourceTree(testkit_api, hid).select_cameras([test_camera_1.name, test_camera_2.name]).create_group()
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.get_group('New Group').has_camera(test_camera_1.name)
        assert rtree.get_group('New Group').has_camera(test_camera_2.name)
        rtree.set_search('New Group')
        ResourceTree(testkit_api, hid).get_group('New Group').remove()
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_camera(test_camera_1.name)
        assert rtree.has_camera(test_camera_2.name)
        assert not rtree.has_group('New Group')


if __name__ == '__main__':
    exit(test_delete_group_in_search_result().main())
