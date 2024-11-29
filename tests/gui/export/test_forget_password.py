# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from distrib import BranchNotSupported
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.layouts import LayoutTabBar
from gui.desktop_ui.messages import InputPasswordDialog
from gui.desktop_ui.messages import ProgressDialog
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_forget_password(VMSTest):
    """Forget password for open file.

    Open protected exported file, input correct password,
    check file content is displayed under the file in resource tree and on the scene;
    close tab with the file, open the file again, input password form does not appear;
    open item of file content in new tab, forget password for open file,
    check tab of the file is closed, video item in new tab disappears,
    file content is not displayed in resource tree under the file.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47295

    Selection-Tag: 47295
    Selection-Tag: export
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            raise BranchNotSupported("Test should be fixed for VMS 6.1+")

        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        video_file = 'samples/time_test_video.mp4'
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, video_file, 2))
        [test_camera_1, test_camera_2] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file=video_file,
            camera_count=2,
            )
        rtree = ResourceTree(testkit_api, hid)
        camera_1_scene_item = rtree.get_camera(test_camera_1.name).open()
        camera_2_scene_item = rtree.get_camera(test_camera_2.name).open()

        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.5)
        export_settings.select_tab('Multi Video')
        export_settings.disable_all_multi_video_features()
        export_settings.multi_export_settings.set_password('123456')
        export_settings.export_with_specific_path(client_installation.temp_dir() / '47295.nov')

        ResourceTree(testkit_api, hid).wait_for_local_file('47295.nov').open()
        input_password_dialog = InputPasswordDialog(testkit_api, hid)
        assert input_password_dialog.is_shown()
        assert "Please enter the password" in input_password_dialog.get_label()
        input_password_dialog.input_password('123456')
        assert input_password_dialog.read_password() == '123456'
        input_password_dialog.click_ok()
        ProgressDialog(testkit_api).wait_until_closed()
        layout_tab_bar = LayoutTabBar(testkit_api, hid)
        assert layout_tab_bar.layout('47295.nov')
        camera_1_scene_item.wait_for_accessible()
        camera_2_scene_item.wait_for_accessible()
        local_file = ResourceTree(testkit_api, hid).get_local_file('47295.nov')
        assert local_file.has_video_item(test_camera_1.name)
        assert local_file.has_video_item(test_camera_2.name)
        layout_tab_bar.close_current_layout()
        file = ResourceTree(testkit_api, hid).get_local_file('47295.nov')
        assert file.has_video_item(test_camera_1.name)
        assert file.has_video_item(test_camera_2.name)
        file.open()
        assert not InputPasswordDialog(testkit_api, hid).is_shown()
        rtree = ResourceTree(testkit_api, hid)
        file = rtree.get_local_file('47295.nov')
        assert file.has_video_item(test_camera_1.name)
        assert file.has_video_item(test_camera_2.name)
        # TODO: Need to fix in VMS 6.1+
        camera_1_scene_item.open_context_menu().open_in_new_tab()
        assert layout_tab_bar.is_open('New Layout 2*')
        camera_1_scene_item.wait_for_accessible()
        rtree.get_local_file('47295.nov').forget_password()
        camera_1_scene_item.wait_for_inaccessible()
        file = ResourceTree(testkit_api, hid).get_local_file('47295.nov')
        assert not file.has_video_item(test_camera_1.name)
        assert not file.has_video_item(test_camera_2.name)
        layout_tab_bar.close_current_layout()
        assert not layout_tab_bar.is_open('47295.nov')
        rtree.get_local_file('47295.nov').open()
        input_password_dialog_2 = InputPasswordDialog(testkit_api, hid)
        assert input_password_dialog_2.is_shown()
        assert "Please enter the password" in input_password_dialog_2.get_label()


if __name__ == '__main__':
    exit(test_forget_password().main())
