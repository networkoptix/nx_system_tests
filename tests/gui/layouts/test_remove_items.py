# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_remove_items(VMSTest):
    """Remove items from Layout.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/816

    Selection-Tag: 816
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
        layout_tab_bar.save_current_as('Remove items')
        rtree = ResourceTree(testkit_api, hid)
        camera_1_scene_item = rtree.get_camera(test_camera_1.name).open()
        camera_2_scene_item = rtree.get_camera(test_camera_2.name).open()
        camera_3_scene_item = rtree.get_camera(test_camera_3.name).open()
        layout_tab_bar.save('Remove items*')
        camera_1_scene_item.click_button('Close')
        camera_1_scene_item.wait_for_inaccessible()
        rtree = ResourceTree(testkit_api, hid)
        assert not rtree.get_layout('Remove items').has_camera(test_camera_1.name)
        assert layout_tab_bar.is_open('Remove items*')
        rtree.get_layout('Remove items').get_camera(test_camera_2.name).remove_from_layout()
        camera_2_scene_item.wait_for_inaccessible()
        rtree = ResourceTree(testkit_api, hid)
        assert not rtree.get_layout('Remove items').has_camera(test_camera_2.name)
        rtree.get_layout('Remove items').get_camera(test_camera_3.name).remove(use_hotkey=True)
        camera_3_scene_item.wait_for_inaccessible()
        assert not ResourceTree(testkit_api, hid).get_layout('Remove items').has_camera(test_camera_3.name)


if __name__ == '__main__':
    exit(test_remove_items().main())
