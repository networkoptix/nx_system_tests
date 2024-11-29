# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import CameraSceneItem
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_add_items_to_layout(VMSTest):
    """Add items to Layout by double click and drag n drop.

    Save layout, add the first camera by drag-n-drop to the layout,
    add the second camera by double click,
    add the third camera by drag-n-drop to the layout icon in resource tree,
    check each camera is open on scene,
    each camera is displayed in resource tree under icon of layout.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/813

    Selection-Tag: 813
    Selection-Tag: layouts
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
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4', 3))
        [test_camera_1, test_camera_2, test_camera_3] = server_vm.api.add_test_cameras(0, 3)
        layout_tab_bar = LayoutTabBar(testkit_api, hid)
        layout_tab_bar.save_current_as('Add items')
        assert layout_tab_bar.is_open('Add items')
        rtree = ResourceTree(testkit_api, hid)
        camera_1_scene_item = rtree.get_camera(test_camera_1.name).drag_n_drop_on_scene()
        rtree.get_camera(test_camera_2.name).open()
        rtree.get_camera(test_camera_3.name).drag_n_drop(rtree.get_layout('Add items'))
        rtree = ResourceTree(testkit_api, hid)
        camera_1_scene_item.wait_for_accessible()
        CameraSceneItem(testkit_api, hid, test_camera_2.name).wait_for_accessible()
        CameraSceneItem(testkit_api, hid, test_camera_3.name).wait_for_accessible()
        assert rtree.get_layout('Add items').has_camera(test_camera_1.name)
        assert rtree.get_layout('Add items').has_camera(test_camera_2.name)
        assert rtree.get_layout('Add items').has_camera(test_camera_3.name)


if __name__ == '__main__':
    exit(test_add_items_to_layout().main())
