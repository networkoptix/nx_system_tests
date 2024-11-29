# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_create_layout_from_tabnav(VMSTest):
    """Create Layout from Tab Navigator.

    Add layout, move a camera on the layout, save it.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/812

    Selection-Tag: 812
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
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        tab_bar = LayoutTabBar(testkit_api, hid)
        tab_bar.add_new_tab()
        ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open()
        tab_bar.wait_for_open('New Layout 2*')
        tab_bar.save('New Layout 2*')
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_layout('New Layout 2')
        assert rtree.get_layout('New Layout 2').has_camera(test_camera_1.name)


if __name__ == '__main__':
    exit(test_create_layout_from_tabnav().main())
