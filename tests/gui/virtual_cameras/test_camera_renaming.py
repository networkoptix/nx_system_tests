# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import extract_start_timestamp
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_camera_renaming(VMSTest):
    """Rename virtual camera.

    Rename virtual camera by context menu

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/42992

    Selection-Tag: 42992
    Selection-Tag: virtual_cameras
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        local_path = gui_prerequisite_store.fetch('upload/mp4.mp4')
        start_time = extract_start_timestamp(local_path)
        camera_id = server_vm.api.add_virtual_camera('VirtualCamera')
        with server_vm.api.virtual_camera_locked(camera_id) as token:
            server_vm.api.upload_to_virtual_camera(camera_id, local_path, token, start_time)
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        rtree = ResourceTree(testkit_api, hid)
        rtree.get_camera('VirtualCamera').cancel_renaming('VirtualCameraUpdated')
        assert rtree.has_camera('VirtualCamera')
        assert not rtree.has_camera('VirtualCameraUpdated')

        rtree.get_camera('VirtualCamera').rename_using_context_menu(new_name='')
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_camera('VirtualCamera')

        rtree.get_camera('VirtualCamera').rename_using_context_menu('VirtualCameraUpdated')
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_camera('VirtualCameraUpdated')
        assert not rtree.has_camera('VirtualCamera')


if __name__ == '__main__':
    exit(test_camera_renaming().main())
