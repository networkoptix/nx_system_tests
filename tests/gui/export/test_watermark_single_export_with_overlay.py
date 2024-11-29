# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.dialogs.export_settings import ExportSettingsDialog
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from os_access import RemotePath
from tests.base_test import VMSTest


class test_watermark_single_export_with_overlay(VMSTest):
    """Success watermark for single export .mkv and .mp4.

    Export mkv and mp4 files, check watermark matches for every file

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20884

    Selection-Tag: 20884
    Selection-Tag: export
    Selection-Tag: watermarks_export
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        [test_camera_1] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file='samples/overlay_test_video.mp4',
            )
        testkit_api, camera_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)

        timeline = Timeline(testkit_api, hid)
        mkv_file_name = '20884.mkv'
        mp4_file_name = '20884.mp4'
        overlay_path = gui_prerequisite_supplier.upload_to_remote('samples/test_image_overlay.png', client_installation.os_access)
        _export_with_overlay(client_installation.temp_dir() / mkv_file_name, str(overlay_path), timeline)
        _export_with_overlay(client_installation.temp_dir() / mp4_file_name, str(overlay_path), timeline)

        rtree = ResourceTree(testkit_api, hid)
        _file_watermark_matched(mkv_file_name, rtree)
        _file_watermark_matched(mp4_file_name, rtree)


def _export_with_overlay(file_path: RemotePath, overlay_path: str, timeline: Timeline):
    export_settings = timeline.open_export_video_dialog_for_interval(0, 0.2)
    export_settings.disable_all_features()
    _set_up_overlay(export_settings, overlay_path)
    export_settings.export_with_specific_path(file_path)


def _file_watermark_matched(file_name: str, rtree: ResourceTree):
    scene_item = rtree.get_local_file(file_name).open_in_new_tab()
    scene_item.wait_for_accessible()
    with scene_item.open_context_menu().open_check_watermark_dialog() as watermark_dialog:
        watermark_dialog.wait_for_matched()


def _set_up_overlay(export_settings: ExportSettingsDialog, overlay_path: str):
    export_settings.timestamp_feature.make_active()
    export_settings.preview.set_timestamp_position('top_left')
    image_feature = export_settings.make_image_feature_active()
    image_feature.set_image(overlay_path)
    image_feature.set_size(500)
    image_feature.set_opacity(100)
    export_settings.preview.set_image_position('bottom_right')


if __name__ == '__main__':
    exit(test_watermark_single_export_with_overlay().main())
