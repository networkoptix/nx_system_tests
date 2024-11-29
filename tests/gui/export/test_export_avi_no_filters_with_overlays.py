# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from doubles.video.vlc_player import VLCPlayer
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.layouts import LayoutTabBar
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


class test_export_avi_no_filters_with_overlays(VMSTest):
    """Apply filters is off and overlays is on and export to avi.

    Set camera AR and rotation, export with overlay but without filters,
    verify overlays and result AR, rotation are default

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20866

    Selection-Tag: 20866
    Selection-Tag: export
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
        testkit_api, camera_scene_item_1 = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)

        bounds = camera_scene_item_1.bounds()
        aspect_ratio = bounds.width / bounds.height
        LayoutTabBar(testkit_api, hid).close_current_layout()

        with ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open_settings() as camera_settings:
            camera_settings.activate_tab('General'.title())
            camera_settings.general_tab.set_aspect_ratio('1:1')
            camera_settings.general_tab.set_image_rotation(180)

        camera_scene_item_2 = ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open_in_new_tab()
        camera_scene_item_2.wait_for_accessible()
        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.9)
        export_settings.disable_all_features()
        export_settings.timestamp_feature.make_active()
        export_settings.preview.set_timestamp_position('top_left')
        overlay_path = gui_prerequisite_supplier.upload_to_remote('samples/test_image_overlay.png', client_installation.os_access)
        image_feature = export_settings.make_image_feature_active()
        image_feature.set_image(str(overlay_path))
        image_feature.set_size(500)
        image_feature.set_opacity(100)
        export_settings.preview.set_image_position('bottom_right')
        text_feature = export_settings.make_text_feature_active()
        text_feature.set_text('test text')
        text_feature.set_size(60)
        text_feature.set_area_width(300)
        export_settings.preview.set_text_position('bottom_left')
        assert text_feature.get_text() == 'test text'
        actual = export_settings.preview.ratio()
        assert abs(aspect_ratio - actual) < 0.1, f"Expected ratio {aspect_ratio}, actual {actual}"
        loaded = SavedImage(gui_prerequisite_store.fetch('test20866/preview.png'))
        preview = export_settings.capture_preview()
        assert preview.is_similar_to(loaded)

        text_position = export_settings.preview.get_text_position()
        image_position = export_settings.preview.get_image_position()
        timestamp_position = export_settings.preview.get_timestamp_position()
        file = client_installation.temp_dir() / 'temp_20866.avi'
        export_settings.export_with_specific_path(file)
        snapshot_path = VLCPlayer(client_installation.os_access).get_preview(file)
        actual_file_path = get_run_dir() / snapshot_path.name
        actual_file_path.write_bytes(snapshot_path.read_bytes())
        actual_image_capture = SavedImage(actual_file_path)
        expected_image_capture = SavedImage(gui_prerequisite_store.fetch('test20866/preview.png'))
        assert actual_image_capture.is_similar_to(expected_image_capture)
        ResourceTree(testkit_api, hid).get_local_file('temp_20866.avi').open_in_new_tab().wait_for_accessible()

        scene = Scene(testkit_api, hid)
        TimelineNavigation(testkit_api, hid).pause_and_to_begin()
        actual_ratio = scene.first_item_image().get_aspect_ratio()
        assert abs(1 - actual_ratio) < 0.02, f"Expected ratio 1, actual {actual_ratio}"
        loaded_screen = SavedImage(gui_prerequisite_store.fetch('test20866/screen.png'))
        scene.wait_until_first_item_is_similar_to(loaded_screen)
        assert scene.get_first_item().has_text_on_position(text_position, ['test text'])
        overlay_piece = scene.first_item_image().crop_percentage(image_position)
        expected_image_overlay = SavedImage(gui_prerequisite_store.fetch('samples/test_image_overlay.png'))
        assert overlay_piece.is_similar_to(expected_image_overlay, crop_border_pixels=2, check_aspect_ratio=False)
        assert scene.get_first_item().has_timestamp_on_position(timestamp_position)


if __name__ == '__main__':
    exit(test_export_avi_no_filters_with_overlays().main())
