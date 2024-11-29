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


class test_multi_export_single_item(VMSTest):
    """Export single item as multi video.

    Open camera with archive, create bookmark, export without description

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/26280

    Selection-Tag: 26280
    Selection-Tag: export
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        [test_camera_1] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file='samples/dynamic_test_video.mp4',
            )
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.9)
        export_settings.select_tab('Multi Video')
        export_settings.disable_all_multi_video_features()
        export_settings.export_with_specific_path(client_installation.temp_dir() / 'temp_26280.nov')
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('temp_26280.nov')
        local_file_node.open_in_new_tab()
        scene = Scene(testkit_api, hid)
        scene.wait_for_items_number(1)

        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.play()
        assert scene.items()[0].video_is_playing()

        timeline_navigation.pause_and_to_begin()
        loaded = SavedImage(gui_prerequisite_store.fetch('test26280/result.png'))
        scene.wait_until_first_item_is_similar_to(loaded)


if __name__ == '__main__':
    exit(test_multi_export_single_item().main())
