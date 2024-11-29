# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_assign_logical_id(VMSTest):
    """User can manually assign Logical ID to camera.

    Set unique camera logical id, check it in server cameras list,
    then try to set the same logical id for another camera, check error message

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/42085

    Selection-Tag: 42085
    Selection-Tag: camera_management
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
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4', 2))
        [test_camera_1, test_camera_2] = server_vm.api.add_test_cameras(0, 2)
        with ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open_settings() as camera_settings:
            camera_settings.activate_tab("Expert")
            camera_settings.expert_tab.set_logical_id(42)

        server = ResourceTree(testkit_api, hid).get_server(server_vm.api.get_server_name())
        camera_list_dialog = server.open_cameras_list()
        assert camera_list_dialog.get_id_for_camera(test_camera_1.name) == 42, (
            "Camera logical ID is incorrect")
        camera_list_dialog.close()
        server.open_add_device_dialog().add_test_cameras(
            test_camera_2.address,
            [test_camera_2.name],
            )
        ResourceTree(testkit_api, hid).wait_for_cameras([test_camera_2.name])
        with ResourceTree(testkit_api, hid).get_camera(test_camera_2.name).open_settings() as camera_settings:
            camera_settings.activate_tab("Expert")
            expert_tab = camera_settings.expert_tab
            expert_tab.set_logical_id(42)
            assert (expert_tab.get_logical_id_warning_text() == f"This ID is already used on the following camera: <b>{test_camera_1.name}</b>")


if __name__ == '__main__':
    exit(test_assign_logical_id().main())
