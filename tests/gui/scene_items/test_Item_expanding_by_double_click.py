# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import extract_start_timestamp
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_Item_expanding_by_double_click(VMSTest):
    """Expanding items to fullscreen by double click.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1876

    Selection-Tag: 1876
    Selection-Tag: scene_items
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        local_file_path = gui_prerequisite_store.fetch('upload/mp4.mp4')
        start_time = extract_start_timestamp(local_file_path)
        camera_id = server_vm.api.add_virtual_camera('VirtualCamera')
        with server_vm.api.virtual_camera_locked(camera_id) as token:
            server_vm.api.upload_to_virtual_camera(camera_id, local_file_path, token, start_time)
        testkit_api, camera_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, 'VirtualCamera')
        hid = HID(testkit_api)
        TimelineNavigation(testkit_api, hid).pause_and_to_begin()
        camera_scene_item.wait_for_window_mode()
        camera_scene_item.change_size_by_double_click()
        camera_scene_item.wait_for_expanded()
        camera_scene_item.change_size_by_double_click()
        camera_scene_item.wait_for_window_mode()


if __name__ == '__main__':
    exit(test_Item_expanding_by_double_click().main())
