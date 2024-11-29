# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import CameraSceneItem
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_moving_group_to_scene(VMSTest):
    """Move groups to the scene.

    Select group and move it to the scene by drag-n-drop. Group is opened on the scene.
    Select several groups and repeat. Groups is opened on the scene

    #  https://networkoptix.testrail.net/index.php?/cases/view/84570

    Selection-Tag: 84570
    Selection-Tag: resources_grouping
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

        ResourceTree(testkit_api, hid).select_cameras([test_camera_1.name]).create_group(use_hotkey=True)
        ResourceTree(testkit_api, hid).select_cameras([test_camera_2.name]).create_group(use_hotkey=True)
        ResourceTree(testkit_api, hid).select_cameras([test_camera_3.name]).create_group(use_hotkey=True)

        ResourceTree(testkit_api, hid).select_groups(['New Group']).drag_n_drop_on_scene()
        CameraSceneItem(testkit_api, hid, test_camera_1.name).wait_for_accessible()
        LayoutTabBar(testkit_api, hid).close_current_layout()

        ResourceTree(testkit_api, hid).select_groups(['New Group 1', 'New Group 2']).drag_n_drop_on_scene()
        Scene(testkit_api, hid).wait_for_items_number(2)
        CameraSceneItem(testkit_api, hid, test_camera_2.name).wait_for_accessible()
        CameraSceneItem(testkit_api, hid, test_camera_3.name).wait_for_accessible()


if __name__ == '__main__':
    exit(test_moving_group_to_scene().main())
