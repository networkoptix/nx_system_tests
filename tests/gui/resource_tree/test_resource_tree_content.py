# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_resource_tree_content(VMSTest):
    """Content of resource tree.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/873

    Selection-Tag: 873
    Selection-Tag: resource_tree
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
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        remote_path = gui_prerequisite_supplier.upload_to_remote('localfiles/dewarped_static_video.mp4', client_installation.os_access)
        MainMenu(testkit_api, hid).open_local_settings_dialog().add_folder(remote_path.parent)
        ResourceTree(testkit_api, hid).wait_for_any_local_file()
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_server(server_vm.api.get_server_name())
        assert rtree.has_camera(test_camera_1.name)
        assert rtree.has_webpage('Home Page')
        assert rtree.has_local_file('dewarped_static_video.mp4')


if __name__ == '__main__':
    exit(test_resource_tree_content().main())
