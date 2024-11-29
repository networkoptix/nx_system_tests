# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.software_cameras import MjpegRtspCameraServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from tests.base_test import VMSTest


class test_remove_rtsp_link(VMSTest):
    """Remove RTSP link.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1021

    Selection-Tag: 1021
    Selection-Tag: camera_management
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        rtsp_server = MjpegRtspCameraServer()
        [rtsp1, rtsp2] = add_cameras(server_vm, rtsp_server, indices=[0, 1])
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        vm_name = server_vm.api.get_server_name()
        exit_stack.enter_context(rtsp_server.async_serve())
        ResourceTree(testkit_api, hid).wait_for_cameras([rtsp1.name, rtsp2.name])
        ResourceTree(testkit_api, hid).get_camera(rtsp1.name).remove()
        assert not ResourceTree(testkit_api, hid).get_server(vm_name).has_camera(rtsp1.name)
        ResourceTree(testkit_api, hid).get_camera(rtsp2.name).remove(use_hotkey=True)
        assert not ResourceTree(testkit_api, hid).get_server(vm_name).has_camera(rtsp2.name)


if __name__ == '__main__':
    exit(test_remove_rtsp_link().main())
