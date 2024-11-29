# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import TimelineNavigation
from gui.desktop_ui.timeline import TimelineTooltip
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_previous_next_chunk(VMSTest):
    """Previous and Next chunk.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1485

    Selection-Tag: 1485
    Selection-Tag: camera_playback
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/dynamic_test_video.mp4'))
        # Test video's length is 40 seconds
        media_file = gui_prerequisite_store.fetch('samples/dynamic_test_video.mp4')
        media_file = SampleMediaFile(media_file)
        [camera] = server_vm.api.add_test_cameras(0, 1)
        now = datetime.now(timezone.utc)
        camera_archive = server_vm.default_archive().camera_archive(camera.physical_id)
        camera_archive.save_media_sample(now - timedelta(minutes=4), media_file)
        camera_archive.save_media_sample(now - timedelta(minutes=3), media_file)
        camera_archive.save_media_sample(now - timedelta(minutes=2), media_file)
        server_vm.api.rebuild_main_archive()
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, camera.name)
        hid = HID(testkit_api)

        scene = Scene(testkit_api, hid)
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.to_prev_chunk()
        assert scene.items()[0].video_is_playing()
        # Minus 40 seconds of chunk and 5 seconds for test actions.
        expected_time = datetime.now() - timedelta(seconds=45)
        timeline_tooltip = TimelineTooltip(testkit_api)
        timeline_tooltip.verify_datetime(expected_time, tolerance=(timedelta(seconds=15)))

        timeline_navigation.to_prev_chunk()
        assert scene.items()[0].video_is_playing()
        # Minus 80 seconds of two chunks, 20 seconds of awaiting, 15 seconds of test actions.
        expected_time = datetime.now() - timedelta(seconds=115)
        timeline_tooltip.verify_datetime(expected_time, tolerance=(timedelta(seconds=15)))

        timeline_navigation.to_next_chunk()
        assert scene.items()[0].video_is_playing()
        # Minus 40 seconds of chunk and 25 seconds for test actions.
        expected_time = datetime.now() - timedelta(seconds=65)
        timeline_tooltip.verify_datetime(expected_time, tolerance=(timedelta(seconds=15)))


if __name__ == '__main__':
    exit(test_previous_next_chunk().main())
