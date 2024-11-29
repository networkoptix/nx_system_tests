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


class test_bookmark_export_no_description(VMSTest):
    """Export bookmark without description.

    Open camera with archive, create bookmark, export without description

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20856

    Selection-Tag: 20856
    Selection-Tag: export
    Selection-Tag: bookmarks
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        [test_camera_1] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file='samples/overlay_test_video.mp4',
            )
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        with ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open_settings() as camera_settings:
            camera_settings.general_tab.reset_image_controls()
        new_bookmark = Timeline(testkit_api, hid).create_bookmark_from_interval_context_menu(
            name='bm',
            description='descr',
            tags='_',
            offset='0',
            width='0.5',
            )
        export_settings = new_bookmark.open_export_bookmark_dialog()

        assert export_settings.is_open()
        assert not export_settings.has_tab('Multi Video')
        bookmark_feature = export_settings.bookmark_feature
        assert bookmark_feature.enabled()
        bookmark_feature.make_active()
        export_settings.bookmark_feature.description_checkbox_is_set()

        export_settings.disable_all_features()
        bookmark_feature = export_settings.make_bookmark_feature_active()
        bookmark_feature.set_size(40)
        bookmark_feature.set_description_checkbox(False)
        export_settings.preview.set_bookmark_position('top_left')
        bookmark_position = export_settings.preview.get_bookmark_position()
        export_settings.export_with_specific_path(client_installation.temp_dir() / 'temp_26293.mkv')
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('temp_26293.mkv')
        local_file_node.open_in_new_tab().wait_for_accessible()

        TimelineNavigation(testkit_api, hid).pause_and_to_begin()
        loaded = SavedImage(gui_prerequisite_store.fetch('test20856/result.png'))
        scene = Scene(testkit_api, hid)
        scene.wait_until_first_item_is_similar_to(loaded)
        assert scene.get_first_item().has_text_on_position(bookmark_position, ['bm'])


if __name__ == '__main__':
    exit(test_bookmark_export_no_description().main())
