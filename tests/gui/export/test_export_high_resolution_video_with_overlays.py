# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_export_high_resolution_video_with_overlays(VMSTest):
    """Export high resolution video with overlays.

    Add default overlays, check they're inside preview, export, validate

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20880

    Selection-Tag: 20880
    Selection-Tag: export
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        server_vm.default_archive().camera_archive(test_camera_1.physical_id).save_media_sample(
            datetime.fromisoformat('2020-11-05T11:11:28+00:00'),
            SampleMediaFile(gui_prerequisite_store.fetch('samples/overlay_test_video.mp4')),
            )
        server_vm.api.rebuild_main_archive()
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)

        timeline = Timeline(testkit_api, hid)
        # Export video to set default values for overlays.
        export_settings_1 = timeline.open_export_video_dialog_for_interval(0, 0.5)
        export_settings_1.disable_all_features()
        export_settings_1.timestamp_feature.make_active()
        export_settings_1.preview.set_timestamp_position('top_left')
        overlay_path = gui_prerequisite_supplier.upload_to_remote('samples/test_image_overlay.png', client_installation.os_access)
        image_feature = export_settings_1.make_image_feature_active()
        image_feature.set_image(str(overlay_path))
        image_feature.set_size(500)
        image_feature.set_opacity(100)
        export_settings_1.preview.set_image_position('bottom_right')
        text_feature = export_settings_1.make_text_feature_active()
        text_feature.set_text('test text')
        text_feature.set_size(60)
        text_feature.set_area_width(300)
        export_settings_1.preview.set_text_position('bottom_left')
        assert text_feature.get_text() == 'test text'
        export_settings_1.export_with_specific_path(client_installation.temp_dir() / 'temp_overlay20880_1.mp4')

        # Export video for which we do validations.
        timeline.click_at_offset(0.9)
        export_settings_2 = timeline.open_export_video_dialog_for_interval(0, 0.5)
        export_settings_2.disable_all_features()
        export_settings_2.timestamp_feature.make_active()
        export_settings_2.image_feature.make_active()
        export_settings_2.text_feature.make_active()
        export_settings_2.preview.validate_overlay_positions()
        loaded_preview = SavedImage(gui_prerequisite_store.fetch('test20880/preview.png'))
        preview = export_settings_2.capture_preview()
        assert preview.is_similar_to(loaded_preview)

        timestamp_position = export_settings_2.preview.get_timestamp_position()
        export_settings_2.export_with_specific_path(client_installation.temp_dir() / 'temp20880.mp4')
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('temp20880.mp4')
        local_file_node.open_in_new_tab().wait_for_accessible()

        scene = Scene(testkit_api, hid)
        TimelineNavigation(testkit_api, hid).pause_and_to_begin()
        loaded_playback = SavedImage(gui_prerequisite_store.fetch('test20880/screen.png'))
        scene.wait_until_first_item_is_similar_to(loaded_playback)
        assert scene.get_first_item().has_timestamp_on_position(timestamp_position)


if __name__ == '__main__':
    exit(test_export_high_resolution_video_with_overlays().main())
