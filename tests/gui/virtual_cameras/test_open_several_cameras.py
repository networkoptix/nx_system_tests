# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import CameraSceneItem
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_open_several_cameras(VMSTest):
    """Open several cameras.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/42994

    Selection-Tag: 42994
    Selection-Tag: virtual_cameras
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        first_virtual_camera_name = 'VirtualCamera1'
        second_virtual_camera_name = 'VirtualCamera2'
        server_vm.api.add_virtual_camera(first_virtual_camera_name)
        server_vm.api.add_virtual_camera(second_virtual_camera_name)
        testkit_api, camera_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            test_camera_1.name,
            )
        hid = HID(testkit_api)
        rtree = ResourceTree(testkit_api, hid)
        remote_file_path = gui_prerequisite_supplier.upload_to_remote('upload/mp4.mp4', client_installation.os_access)
        with rtree.get_camera(first_virtual_camera_name).open_settings() as camera_settings:
            camera_settings.general_tab.open_upload_file_dialog().upload_file(
                str(remote_file_path),
                time_sleep=20)
        with rtree.get_camera(second_virtual_camera_name).open_settings() as camera_settings:
            camera_settings.general_tab.open_upload_file_dialog().upload_file(
                str(remote_file_path),
                time_sleep=20)
        last_selected_camera = ResourceTree(testkit_api, hid).select_cameras([first_virtual_camera_name, second_virtual_camera_name])
        last_selected_camera.open_by_context_menu()
        Scene(testkit_api, hid).wait_for_items_number(3)
        assert LayoutTabBar(testkit_api, hid).is_open('TestLayout*')
        first_virtual_camera_item = CameraSceneItem(testkit_api, hid, first_virtual_camera_name)
        second_virtual_camera_item = CameraSceneItem(testkit_api, hid, second_virtual_camera_name)
        assert first_virtual_camera_item.has_phrase("NO LIVE STREAM")
        assert second_virtual_camera_item.has_phrase("NO LIVE STREAM")
        TimelineNavigation(testkit_api, hid).to_prev_chunk()
        assert first_virtual_camera_item.video_is_playing()
        assert second_virtual_camera_item.video_is_playing()


if __name__ == '__main__':
    exit(test_open_several_cameras().main())
