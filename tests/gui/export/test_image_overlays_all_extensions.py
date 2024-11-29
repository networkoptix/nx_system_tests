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
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_image_overlays_all_extensions(VMSTest):
    """Export video with different image types as overlays.

    Add image when exporting, verify when exported

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20877

    Selection-Tag: 20877
    Selection-Tag: export
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
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
        for files in [
            ['test20877/image.jpg', 'temp_20877_jpg.mp4'],
            ['test20877/image.png', 'temp_20877_png.mp4'],
            ['test20877/image.gif', 'temp_20877_gif.mp4'],
            ['test20877/image.tiff', 'temp_20877_tiff.mp4'],
            ['test20877/image.bmp', 'temp_20877_bmp.mp4'],
            ['test20877/image.jpeg', 'temp_20877_jpeg.mp4'],
            ['test20877/image.pgm', 'temp_20877_pgm.mp4'],
                ]:
            [image_path, file_name] = files

            export_settings = timeline.open_export_video_dialog_for_interval(0, 0.9)
            export_settings.disable_all_features()
            path = gui_prerequisite_supplier.upload_to_remote(image_path, client_installation.os_access)
            image_feature = export_settings.make_image_feature_active()
            image_feature.set(str(path))
            export_settings.export_with_specific_path(client_installation.temp_dir() / file_name)
            local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file(file_name)
            local_file_node.open_in_new_tab().wait_for_accessible()

            TimelineNavigation(testkit_api, hid).pause_and_to_begin()
            loaded = SavedImage(gui_prerequisite_store.fetch('test20877/result.png'))
            Scene(testkit_api, hid).wait_until_first_item_is_similar_to(loaded)
            LayoutTabBar(testkit_api, hid).close_current_layout()


if __name__ == '__main__':
    exit(test_image_overlays_all_extensions().main())
