# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import CameraSceneItem
from gui.desktop_ui.scene_items import ServerSceneItem
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_open_multiple_items_in_new_tab(VMSTest):
    """Open multiple selected items from tree in new tab and save.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1170

    Selection-Tag: 1170
    Selection-Tag: layouts
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
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4', 2))
        [test_camera_1, test_camera_2] = server_vm.api.add_test_cameras(0, 2)
        rtree = ResourceTree(testkit_api, hid)
        assert not rtree.has_layout('New Layout 1')
        assert not rtree.has_layout('New Layout 2')
        rtree.get_camera(test_camera_1.name).select()
        rtree.get_camera(test_camera_2.name).select()
        server_name = server_vm.api.get_server_name()
        rtree.get_server(server_name).select()
        rtree.get_camera(test_camera_1.name).open_in_new_tab()
        CameraSceneItem(testkit_api, hid, test_camera_1.name).wait_for_accessible()
        CameraSceneItem(testkit_api, hid, test_camera_2.name).wait_for_accessible()
        ServerSceneItem(testkit_api, hid, server_name).wait_for_accessible()

        hid.keyboard_hotkeys('Ctrl', 'S')
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_layout('New Layout 2')
        assert rtree.get_layout('New Layout 2').has_camera(test_camera_1.name)
        assert rtree.get_layout('New Layout 2').has_camera(test_camera_2.name)
        assert rtree.get_layout('New Layout 2').has_server_monitoring(server_name)


if __name__ == '__main__':
    exit(test_open_multiple_items_in_new_tab().main())
