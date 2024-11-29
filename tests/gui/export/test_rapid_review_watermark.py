# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_rapid_review_watermark(VMSTest):
    """Success watermark for rapid review.

    Open exported rapid review video, check watermark is matched

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20886

    Selection-Tag: 20886
    Selection-Tag: export
    Selection-Tag: watermarks_export
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        server_vm.default_archive().camera_archive(test_camera_1.physical_id).save_media_sample(
            datetime.fromisoformat('2020-12-05T11:11:28+00:00'),
            SampleMediaFile(gui_prerequisite_store.fetch('samples/overlay_test_video.mp4')),
            )
        server_vm.api.rebuild_main_archive()
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.2)
        export_settings.disable_all_features()
        export_settings.rapid_review_feature.make_active()
        export_settings.timestamp_feature.make_active()
        export_settings.preview.set_timestamp_position('top_left')
        overlay_path = gui_prerequisite_supplier.upload_to_remote('samples/test_image_overlay.png', client_installation.os_access)
        image_feature = export_settings.make_image_feature_active()
        image_feature.set_image(str(overlay_path))
        image_feature.set_size(500)
        image_feature.set_opacity(100)
        export_settings.preview.set_image_position('bottom_right')
        export_settings.export_with_specific_path(client_installation.temp_dir() / 'temp_20886.avi')
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('temp_20886.avi')
        scene_item = local_file_node.open_in_new_tab()
        scene_item.wait_for_accessible()
        with scene_item.open_context_menu().open_check_watermark_dialog() as watermark_dialog:
            watermark_dialog.wait_for_matched()


if __name__ == '__main__':
    exit(test_rapid_review_watermark().main())
