# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
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
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_image_overlay_opacity(VMSTest):
    """Export video with image overlay of different size and opacity.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20878

    Selection-Tag: 20878
    Selection-Tag: export
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

        timeline = Timeline(testkit_api, hid)
        export_settings_1 = timeline.open_export_video_dialog_for_interval(0, 0.9)
        export_settings_1.disable_all_features()
        image_path = gui_prerequisite_supplier.upload_to_remote('samples/test_image_overlay.png', client_installation.os_access)
        image_feature = export_settings_1.make_image_feature_active()
        image_feature.set(str(image_path), 200, 80, 'bottom_right')
        export_settings_1.export_with_specific_path(client_installation.temp_dir() / 'temp20878.mp4')
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('temp20878.mp4')
        local_file_node.open_in_new_tab().wait_for_accessible()

        scene = Scene(testkit_api, hid)
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause_and_to_begin()
        loaded = SavedImage(gui_prerequisite_store.fetch('test20878/result1.png'))
        scene.wait_until_first_item_is_similar_to(loaded)
        LayoutTabBar(testkit_api, hid).close_current_layout()

        # Check other export parameters
        export_settings_2 = timeline.open_export_video_dialog_for_interval(0, 0.9)
        export_settings_2.disable_all_features()
        image_feature = export_settings_2.make_image_feature_active()
        image_feature.set(str(image_path), 800, 20, 'bottom_right')
        export_settings_2.export_with_specific_path(client_installation.temp_dir() / 'temp20878_2.mp4')
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('temp20878_2.mp4')
        local_file_node.open_in_new_tab().wait_for_accessible()

        timeline_navigation.pause_and_to_begin()
        loaded = SavedImage(gui_prerequisite_store.fetch('test20878/result2.png'))
        scene.wait_until_first_item_is_similar_to(loaded)


if __name__ == '__main__':
    exit(test_image_overlay_opacity().main())
