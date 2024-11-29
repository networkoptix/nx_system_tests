# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_remove_offline_camera_in_resource_tree(VMSTest):
    """Remove offline camera in resource tree.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1016

    Selection-Tag: 1016
    Selection-Tag: camera_management
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
        with playing_testcamera(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4'):
            [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
            ResourceTree(testkit_api, hid).wait_for_camera_on_server(
                server_vm.api.get_server_name(), test_camera_1.name)
        # Stopping testcamera early to reduce waiting time of offline state in resource tree
        ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open()
        assert ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).is_offline()

        ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).start_removing()
        MessageBox(testkit_api, hid).close_by_button('Cancel')

        ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).start_removing()
        MessageBox(testkit_api, hid).close_by_button('Delete')
        assert not ResourceTree(testkit_api, hid).has_camera(test_camera_1.name)

        time.sleep(20)
        assert not ResourceTree(testkit_api, hid).has_camera(test_camera_1.name)


if __name__ == '__main__':
    exit(test_remove_offline_camera_in_resource_tree().main())
