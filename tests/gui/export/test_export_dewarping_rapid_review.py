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
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_export_dewarping_rapid_review(VMSTest):
    """Export dewarping.

    Export rapid review for dewarped camera with and without filters, verify exported videos

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20926

    Selection-Tag: 20926
    Selection-Tag: export
    Selection-Tag: dewarping
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file='samples/overlay_test_video.mp4',
            )
        testkit_api, camera_scene_item_1 = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        with ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open_settings() as camera_settings:
            camera_settings.activate_tab('Dewarping')
            camera_settings.dewarping_tab.enable_dewarping()

        timeline = Timeline(testkit_api, hid)
        camera_scene_item_1.activate_button('Dewarping')
        camera_scene_item_1.set_dewarping('180')
        export_settings_1 = timeline.open_export_video_dialog_for_interval(0, 0.2)
        export_settings_1.disable_all_features()
        export_settings_1.single_camera_settings.set_apply_filters(True)
        export_settings_1.rapid_review_feature.make_active()
        export_settings_1.export_with_specific_path(client_installation.temp_dir() / '20926_with_filters.avi')
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('20926_with_filters.avi')
        local_file_node.open_in_new_tab().wait_for_accessible()
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause()
        loaded_with_filters = SavedImage(gui_prerequisite_store.fetch('test20926/with_filters.png'))
        scene = Scene(testkit_api, hid)
        scene.wait_until_first_item_is_similar_to(loaded_with_filters)

        camera_scene_item_2 = ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open_in_new_tab()
        camera_scene_item_2.wait_for_accessible()
        camera_scene_item_2.activate_button('Dewarping')
        camera_scene_item_2.set_dewarping('180')
        export_settings_2 = timeline.open_export_video_dialog_for_interval(0, 0.2)
        export_settings_2.disable_all_features()
        export_settings_2.single_camera_settings.set_apply_filters(False)
        export_settings_2.rapid_review_feature.make_active()
        export_settings_2.export_with_specific_path(client_installation.temp_dir() / '20926_without_filters.avi')
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('20926_without_filters.avi')
        local_file_node.open_in_new_tab().wait_for_accessible()
        timeline_navigation.pause()
        loaded_without_filters = SavedImage(gui_prerequisite_store.fetch('test20926/without_filters.png'))
        scene.wait_until_first_item_is_similar_to(loaded_without_filters)


if __name__ == '__main__':
    exit(test_export_dewarping_rapid_review().main())
