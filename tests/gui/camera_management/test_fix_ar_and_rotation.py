# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_fix_ar_and_rotation(VMSTest):
    """Set fix aspect ratio and rotation.

    Set non-default aspect ratio and rotation for the camera, check these changes

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/954

    Selection-Tag: 954
    Selection-Tag: camera_management
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        # Default aspect ratio of the camera must be 16:9

        scene = Scene(testkit_api, hid)
        actual = scene.first_item_image().get_aspect_ratio()
        assert abs(16 / 9 - actual) < 0.02, f"Expected ratio 16/9, actual {actual}"

        with ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open_settings() as camera_settings:
            camera_settings.general_tab.set_aspect_ratio('4:3')
            camera_settings.general_tab.set_image_rotation(90)
        LayoutTabBar(testkit_api, hid).close_current_layout()
        ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open()
        actual1 = scene.first_item_image().get_aspect_ratio()
        assert abs(3 / 4 - actual1) < 0.02, f"Expected ratio 3/4, actual {actual1}"


if __name__ == '__main__':
    exit(test_fix_ar_and_rotation().main())
