# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_select_items_on_scene_by_dragging_and_hotkey(VMSTest):
    """Select items on scene by dragging and hotkey.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1179

    Selection-Tag: 1179
    Selection-Tag: layouts
    Selection-Tag: scene_items
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        # same video for multiple cameras
        similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4', 4)
        [test_camera_1, test_camera_2, test_camera_3, test_camera_4] = server_vm.api.add_test_cameras(0, 4)
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        scene = Scene(testkit_api, hid)
        camera_names = [test_camera_1.name, test_camera_2.name, test_camera_3.name, test_camera_4.name]
        ResourceTree(testkit_api, hid).select_cameras(camera_names).open_by_context_menu()
        scene.wait_for_items_number(len(camera_names))
        scene.select_items_dragging(2)
        assert 2 == len([item for item in scene.items() if item.is_selected()])
        hid.keyboard_hotkeys('Ctrl', 'A')
        assert 4 == len([item1 for item1 in scene.items() if item1.is_selected()])


if __name__ == '__main__':
    exit(test_select_items_on_scene_by_dragging_and_hotkey().main())
