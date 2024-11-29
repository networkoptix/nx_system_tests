# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
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


class test_several_password_protected(VMSTest):
    """Open several password protected files at once.

    Open simultaneously two password protected exported files,
    check input password form appears for every protected file,
    check new tab is open for every file, playback is correct.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47287

    Selection-Tag: 47287
    Selection-Tag: export
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
        video_file = 'samples/overlay_test_video.mp4'
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, video_file, 2))
        [test_camera_1, test_camera_2] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file=video_file,
            camera_count=2,
            )
        rtree = ResourceTree(testkit_api, hid)
        camera_1_scene_item = rtree.get_camera(test_camera_1.name).open()
        camera_2_scene_item = rtree.get_camera(test_camera_2.name).open()

        timeline = Timeline(testkit_api, hid)
        export_settings_1 = timeline.open_export_video_dialog_for_interval(0, 0.5)
        export_settings_1.select_tab('Multi Video')
        export_settings_1.disable_all_multi_video_features()
        export_settings_1.multi_export_settings.set_password('123456')
        export_settings_1.export_with_specific_path(client_installation.temp_dir() / '47287.nov')

        timeline.click_at_offset(0.9)
        export_settings_2 = timeline.open_export_video_dialog_for_interval(0, 0.5)
        export_settings_2.select_tab('Multi Video')
        export_settings_2.disable_all_multi_video_features()
        export_settings_2.multi_export_settings.set_password('123456')
        export_settings_2.export_with_specific_path(client_installation.temp_dir() / '47287.exe')
        ResourceTree(testkit_api, hid).wait_for_any_local_file()

        ResourceTree(testkit_api, hid).select_files(['47287.nov', '47287.exe']).drag_n_drop_on_scene()
        input_password_dialog_1 = InputPasswordDialog(testkit_api, hid)
        input_password_dialog_1.input_password('123456')
        input_password_dialog_1.click_ok()
        ProgressDialog(testkit_api).wait_until_closed()
        layout_tab_bar = LayoutTabBar(testkit_api, hid)
        assert layout_tab_bar.layout('47287.nov')
        assert layout_tab_bar.layout('47287.exe')
        camera_1_scene_item.wait_for_accessible()
        camera_2_scene_item.wait_for_accessible()
        layout_tab_bar.close_current_layout()
        camera_1_scene_item.wait_for_accessible()
        camera_2_scene_item.wait_for_accessible()


if __name__ == '__main__':
    exit(test_several_password_protected().main())
