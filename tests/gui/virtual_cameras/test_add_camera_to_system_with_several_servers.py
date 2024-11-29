# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.camera_settings import CameraSettingsDialog
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_systems
from tests.base_test import VMSTest


class test_add_camera_to_system_with_several_servers(VMSTest):
    """Adding virtual camera to a system with several servers.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/41519

    Selection-Tag: 41519
    Selection-Tag: virtual_cameras
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, server_vm2, client_installation] = exit_stack.enter_context(machine_pool.setup_two_servers_client())
        merge_systems(server_vm, server_vm2, take_remote_settings=False)
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        server_vm_name = server_vm.api.get_server_name()
        server_vm2_name = server_vm2.api.get_server_name()
        virtual_camera_dialog = MainMenu(testkit_api, hid).activate_new_virtual_camera()
        assert virtual_camera_dialog.get_current_camera_name() == 'Virtual Camera'
        assert virtual_camera_dialog.get_current_server_name() == server_vm_name
        available_servers = virtual_camera_dialog.get_available_servers()
        assert {server_vm_name, server_vm2_name} == set(available_servers)
        virtual_camera_dialog.add_virtual_camera(server_name=server_vm2_name)
        server_vm2_node = ResourceTree(testkit_api, hid).get_server(server_vm2_name)
        assert server_vm2_node.get_all_cameras().keys() == {'Virtual Camera'}
        with CameraSettingsDialog(testkit_api, hid).wait_until_appears() as camera_settings:
            camera_settings.general_tab.set_image_rotation(90)
            camera_settings.general_tab.set_min_keep_archive(1)
            camera_settings.general_tab.set_max_keep_archive(12)
            camera_settings.general_tab.set_ignore_time_zone(False)
            camera_settings.general_tab.set_detection_sensitivity(1)

        with ResourceTree(testkit_api, hid).get_camera('Virtual Camera').open_settings() as camera_settings:
            assert camera_settings.general_tab.get_image_rotation() == '90 degrees'
            assert camera_settings.general_tab.get_min_keep_archive() == '1'
            assert camera_settings.general_tab.get_min_keep_archive_unit() == 'Day'
            assert camera_settings.general_tab.get_max_keep_archive() == '12'
            assert camera_settings.general_tab.get_max_keep_archive_unit() == 'Days'
            assert not camera_settings.general_tab.get_ignore_time_zone()
            assert camera_settings.general_tab.get_detection_sensitivity() == '1'


if __name__ == '__main__':
    exit(test_add_camera_to_system_with_several_servers().main())
