# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_enable_disable_dewarping(VMSTest):
    """Enable disable dewarping.

    Enable dewarping for the camera in general, check dewarping is off for the new item by default,
    then activate dewarping mode for the item, check it

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1235

    Selection-Tag: 1235
    Selection-Tag: camera_management
    Selection-Tag: dewarping
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
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        with ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open_settings() as camera_settings:
            camera_settings.activate_tab('dewarping'.title())
            camera_settings.dewarping_tab.enable_dewarping()
        camera_scene_item = ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open_in_new_tab()
        camera_scene_item.wait_for_accessible()
        assert not camera_scene_item.button_checked('Dewarping')
        camera_scene_item.activate_button('Dewarping')
        assert camera_scene_item.button_checked('Dewarping')
        assert camera_scene_item.get_dewarping_value() == "90"
        ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).remove()


if __name__ == '__main__':
    exit(test_enable_disable_dewarping().main())
