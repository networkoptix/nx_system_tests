# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.media_capturing import SavedImage
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_text_overlay_area_and_size(VMSTest):
    """Check text overlay with different area and font size.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20883

    Selection-Tag: 20883
    Selection-Tag: export
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        [test_camera_1] = testcameras_with_just_recorded_archive(nx_server=server_vm, video_file='samples/overlay_test_video.mp4')
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        timeline = Timeline(testkit_api, hid)
        export_settings_1 = timeline.open_export_video_dialog_for_interval(0, 0.9)
        export_settings_1.select_tab('Single Camera')
        export_settings_1.disable_all_features()
        text_feature = export_settings_1.make_text_feature_active()
        text_feature.set_text('New Text')
        text_feature.set_size(50)
        text_feature.set_area_width(300)
        export_settings_1.preview.set_text_position('top_center')
        assert text_feature.get_text() == 'New Text'
        text_position = export_settings_1.preview.get_text_position()
        filename = 'temp_20883.mkv'
        export_settings_1.export_with_specific_path(client_installation.temp_dir() / filename)
        ResourceTree(testkit_api, hid).get_local_file(filename).open_in_new_tab().wait_for_accessible()

        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause_and_to_begin()
        loaded_playback = SavedImage(gui_prerequisite_store.fetch('test20883/result1.png'))
        scene = Scene(testkit_api, hid)
        scene.wait_until_first_item_is_similar_to(loaded_playback)
        assert scene.get_first_item().has_text_on_position(text_position, ['New Text'])

        # Check other overlay parameters
        camera_scene_item = ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open_in_new_tab()
        camera_scene_item.wait_for_accessible()
        export_settings_2 = timeline.open_export_video_dialog_for_interval(0, 0.9)
        export_settings_2.select_tab('Single Camera')
        export_settings_2.disable_all_features()
        text_feature = export_settings_2.make_text_feature_active()
        text_feature.set_text('test text')
        text_feature.set_size(100)
        text_feature.set_area_width(700)
        export_settings_2.preview.set_text_position('bottom_left')
        assert text_feature.get_text() == 'test text'
        text_position = export_settings_2.preview.get_text_position()
        filename = 'temp_20883.mp4'
        export_settings_2.export_with_specific_path(client_installation.temp_dir() / filename)
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file(filename)
        local_file_node.open_in_new_tab().wait_for_accessible()

        timeline_navigation.pause_and_to_begin()
        loaded_playback = SavedImage(gui_prerequisite_store.fetch('test20883/result2.png'))
        scene.wait_until_first_item_is_similar_to(loaded_playback)
        assert scene.get_first_item().has_text_on_position(text_position, ['test text'])


if __name__ == '__main__':
    exit(test_text_overlay_area_and_size().main())
