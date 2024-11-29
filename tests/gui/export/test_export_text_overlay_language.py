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


class test_export_text_overlay_language(VMSTest):
    """Different languages for russian and english and chinese.

    Add text with English, Russian and Chinese into text overlay of export,
    check export is correct, all symbols are displayed correctly.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/20882

    Selection-Tag: 20882
    Selection-Tag: export
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = testcameras_with_just_recorded_archive(nx_server=server_vm, video_file='samples/overlay_test_video.mp4')
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)

        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.2)
        export_settings.disable_all_features()
        text_feature = export_settings.make_text_feature_active()
        text_feature.set_text('New Text Новый текст 新的文本')
        text_feature.set_size(60)
        text_feature.set_area_width(300)
        export_settings.preview.set_text_position('bottom_left')
        assert text_feature.get_text() == 'New Text Новый текст 新的文本'
        export_settings.export_with_specific_path(client_installation.temp_dir() / 'multilang.avi')
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('multilang.avi')
        local_file_node.open_in_new_tab().wait_for_accessible()
        TimelineNavigation(testkit_api, hid).pause()
        loaded = SavedImage(gui_prerequisite_store.fetch('test20882/multilang.png'))
        Scene(testkit_api, hid).wait_until_first_item_is_similar_to(loaded)


if __name__ == '__main__':
    exit(test_export_text_overlay_language().main())
