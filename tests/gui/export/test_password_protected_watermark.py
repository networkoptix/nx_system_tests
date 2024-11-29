# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.messages import InputPasswordDialog
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import testcameras_with_archive
from tests.base_test import VMSTest


class test_password_protected_watermark(VMSTest):
    """Success watermark for password-protected file.

    Export nov and exe password-protected files with two cameras,
    open them and check watermark for each item.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47294

    Selection-Tag: unstable
    Selection-Tag: 47294
    Selection-Tag: export
    Selection-Tag: watermarks_export
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
        [test_camera_1, test_camera_2] = testcameras_with_archive(
            nx_server=server_vm,
            video_file='samples/time_test_video.mp4',
            camera_count=2,
            offset_from_now_sec=24 * 3600,
            )
        rtree = ResourceTree(testkit_api, hid)
        camera_1_scene_item = rtree.get_camera(test_camera_1.name).open()
        camera_2_scene_item = rtree.get_camera(test_camera_2.name).open()

        timeline = Timeline(testkit_api, hid)
        export_settings_1 = timeline.open_export_video_dialog_for_interval(0, 0.5)
        export_settings_1.select_tab('Multi Video')
        export_settings_1.disable_all_multi_video_features()
        export_settings_1.multi_export_settings.set_password('123456')
        export_settings_1.export_with_specific_path(client_installation.temp_dir() / '47294.nov')

        timeline.click_at_offset(0.9)
        export_settings_2 = timeline.open_export_video_dialog_for_interval(0, 0.5)
        export_settings_2.select_tab('Multi Video')
        export_settings_2.disable_all_multi_video_features()
        export_settings_2.multi_export_settings.set_password('123456')
        export_settings_2.export_with_specific_path(client_installation.temp_dir() / '47294.exe')

        ResourceTree(testkit_api, hid).get_local_file('47294.nov').open()
        input_password_dialog = InputPasswordDialog(testkit_api, hid)
        input_password_dialog.input_password('123456')
        input_password_dialog.click_ok()
        input_password_dialog.wait_until_closed()
        with camera_1_scene_item.open_context_menu().open_check_watermark_dialog() as watermark_dialog:
            watermark_dialog.wait_for_matched()
        with camera_2_scene_item.open_context_menu().open_check_watermark_dialog() as watermark_dialog:
            watermark_dialog.wait_for_matched()
        ResourceTree(testkit_api, hid).get_local_file('47294.exe').open()
        dialog = InputPasswordDialog(testkit_api, hid)
        dialog.input_password('123456')
        dialog.click_ok()
        dialog.wait_until_closed()
        with camera_1_scene_item.open_context_menu().open_check_watermark_dialog() as watermark_dialog:
            watermark_dialog.wait_for_matched()
        with camera_2_scene_item.open_context_menu().open_check_watermark_dialog() as watermark_dialog:
            watermark_dialog.wait_for_matched()


if __name__ == '__main__':
    exit(test_password_protected_watermark().main())
