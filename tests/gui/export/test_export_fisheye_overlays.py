# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from distrib import BranchNotSupported
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


class test_export_fisheye_overlays(VMSTest):
    """Export fish eye camera without filters and with overlays to mkv.

    Verify export preview and exported video with all overlays and with dewarped view
    if in export video dialog applying filters is disabled

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20869

    Selection-Tag: 20869
    Selection-Tag: export
    Selection-Tag: dewarping
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            raise BranchNotSupported("Test should be fixed for VMS 6.1+")

        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        server_vm.default_archive().camera_archive(test_camera_1.physical_id).save_media_sample(
            datetime.fromisoformat('2021-01-01T11:11:11+00:00'),
            SampleMediaFile(gui_prerequisite_store.fetch('samples/overlay_test_video.mp4')),
            )
        server_vm.api.rebuild_main_archive()
        testkit_api, camera_scene_item = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        with ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).open_settings() as camera_settings:
            camera_settings.activate_tab('Dewarping')
            camera_settings.dewarping_tab.enable_dewarping()
        camera_scene_item.activate_button('Dewarping')
        camera_scene_item.set_dewarping('360')
        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.2)
        export_settings.disable_all_features()
        export_settings.single_camera_settings.set_apply_filters(False)
        export_settings.timestamp_feature.make_active()
        export_settings.preview.set_timestamp_position('top_left')
        overlay_path = gui_prerequisite_supplier.upload_to_remote('samples/test_image_overlay.png', client_installation.os_access)
        image_feature = export_settings.make_image_feature_active()
        image_feature.set_image(str(overlay_path))
        image_feature.set_size(500)
        image_feature.set_opacity(100)
        export_settings.preview.set_image_position('bottom_right')
        text_feature = export_settings.make_text_feature_active()
        text_feature.set_text('TestText')
        text_feature.set_size(60)
        text_feature.set_area_width(300)
        export_settings.preview.set_text_position('bottom_left')
        assert text_feature.get_text() == 'TestText'
        loaded_preview = SavedImage(gui_prerequisite_store.fetch('test20869/preview.png'))
        actual_preview = export_settings.capture_preview()
        # TODO: Need to fix in VMS 6.1+
        assert actual_preview.is_similar_to(loaded_preview)
        export_settings.export_with_specific_path(client_installation.temp_dir() / 'temp_20869.mkv')
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('temp_20869.mkv')
        local_file_node.open_in_new_tab().wait_for_accessible()
        TimelineNavigation(testkit_api, hid).pause()
        loaded_playback = SavedImage(gui_prerequisite_store.fetch('test20869/playback.png'))
        Scene(testkit_api, hid).wait_until_first_item_is_similar_to(loaded_playback)


if __name__ == '__main__':
    exit(test_export_fisheye_overlays().main())
