# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import timedelta

from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_export_bookmark_by_button_on_timeline(VMSTest):
    """Export bookmark from timeline bookmark tooltip and check its validity.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30451

    Selection-Tag: 30451
    Selection-Tag: bookmarks
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4'))
        [test_camera_1] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            camera_count=1,
            video_file='samples/time_test_video.mp4',
            )

        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        timeline = Timeline(testkit_api, hid)
        new_bookmark = timeline.create_bookmark_from_interval_context_menu(
            name='bm',
            description='description',
            tags='_',
            offset='0',
            width='0.9',
            )
        export_settings = new_bookmark.open_export_bookmark_dialog_using_tooltip()
        assert export_settings.is_open()
        assert not export_settings.has_tab('Multi Video')
        assert export_settings.bookmark_feature.enabled()

        export_settings.export_with_specific_path(client_installation.temp_dir() / 'temp_26293.mkv')
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('temp_26293.mkv')
        local_file_node.open_in_new_tab().wait_for_accessible()
        assert Scene(testkit_api, hid).items()[0].video_is_playing()

        # Expect test video length to be 8 minutes, we export it wholly in a bookmark so it must be 2 minutes long
        expected_length = timedelta(minutes=8)
        video_length = timeline.get_current_length()
        assert abs(video_length - expected_length) < timedelta(seconds=5), (
            f'Expected test video length: {expected_length}, Actual: {video_length}'
            )


if __name__ == '__main__':
    exit(test_export_bookmark_by_button_on_timeline().main())
