# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_chunk_appearance(VMSTest):
    """Check archive displayed properly on timeline when navigating through it.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/2809

    Selection-Tag: 2809
    Selection-Tag: camera_playback
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        video_file = 'samples/overlay_test_video.mp4'
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, video_file))
        [test_camera_1] = testcameras_with_just_recorded_archive(
            server_vm, video_file=video_file)
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        TimelineNavigation(testkit_api, hid).pause()
        timeline = Timeline(testkit_api, hid)
        chunk_count = timeline.count_archive_chunks()
        expected_chunk_count = 1
        assert chunk_count == expected_chunk_count, (
            f'Expected archive chunks: {expected_chunk_count}, Actual count: {chunk_count}'
            )
        timeline.zoom_to_archive_chunk()
        chunk_count = timeline.count_archive_chunks()
        assert chunk_count == expected_chunk_count, (
            f'Expected archive chunks: {expected_chunk_count}, Actual count: {chunk_count}'
            )


if __name__ == '__main__':
    exit(test_chunk_appearance().main())
