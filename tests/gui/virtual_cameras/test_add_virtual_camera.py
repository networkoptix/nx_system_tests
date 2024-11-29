# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.camera_settings import CameraSettingsDialog
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_add_virtual_camera(VMSTest):
    """Adding virtual camera.

    Add virtual camera, upload suitable video, check camera on the layout,
    edit camera settings and check changes

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/41490

    Selection-Tag: 41490
    Selection-Tag: virtual_cameras
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
        new_virtual_camera = MainMenu(testkit_api, hid).activate_new_virtual_camera()
        new_virtual_camera.add_virtual_camera('VirtualCamera')
        remote_file_path = gui_prerequisite_supplier.upload_to_remote('upload/mp4.mp4', client_installation.os_access)
        with CameraSettingsDialog(testkit_api, hid) as camera_settings:
            camera_settings.general_tab.open_upload_file_dialog().upload_file(
                str(remote_file_path),
                time_sleep=20)
            camera_settings.general_tab.get_ignore_time_zone_check_box().set(True)
            camera_settings.general_tab.set_image_rotation(90)
        rtree = ResourceTree(testkit_api, hid)
        with rtree.get_camera('VirtualCamera').open_settings() as camera_settings:
            assert camera_settings.general_tab.get_ignore_time_zone_check_box().is_checked()
            assert camera_settings.general_tab.get_image_rotation() == '90 degrees'
        rtree.get_camera('VirtualCamera').open()


if __name__ == '__main__':
    exit(test_add_virtual_camera().main())
