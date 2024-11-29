# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.ocr import ImageDigitsRecognition
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_playback_speed(VMSTest):
    """Playback speed.

    time test video length is 8 minutes
    2x expected time: 4 minutes
    4x expected time: 2 minutes
    8x expected time: 1 minutes
    16x expected time: 30 seconds
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1486

    Selection-Tag: 1489
    Selection-Tag: camera_playback
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        [test_camera_1] = testcameras_with_just_recorded_archive(server_vm, video_file='samples/time_test_video.mp4')
        """
        To determine the speed we need to count number of seconds passed on video and in real life
        And then we compare expected number of seconds with real one taking into account speed and deviation
        We take a special video which shows current number of seconds passed from beginning.
        It lasts 120 seconds, so one number corresponds to 1 second at normal speed.
        If we go forward => starting_number is 0.
        If we go backward => starting_number is 120.
        """
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)

        def _sleep_for(measuring_seconds: int):
            """Sleep for measuring seconds.

            We assume when this step is called, we have the starting number of video set on screen
            and video IS ALREADY PLAYING in desired direction.
            Measuring_time - how many seconds we want to measure playback speed, it may differ.
            We wait for measuring_time, then stop playback
            """
            time.sleep(measuring_seconds)
            timeline_navigation.pause()

        def _recognize_and_find_expected_speed_in_interval(expected_video_sec: int, delta: float):
            # Check the speed of playback by means of time_test_video.
            numeric_comparer = ImageDigitsRecognition(Scene(testkit_api, hid).first_item_image())
            return numeric_comparer.has_in_delta_neighborhood(expected_video_sec, delta)

        # Forward
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.pause_and_to_begin()
        timeline_navigation.play()
        timeline_navigation.increase_speed_2x()
        _sleep_for(30)
        expected_video_sec, delta = _calculate_slide_and_delta(30, 0, 2)
        assert _recognize_and_find_expected_speed_in_interval(expected_video_sec, delta)

        timeline_navigation.pause_and_to_begin()
        timeline_navigation.play()
        timeline_navigation.increase_speed_2x()
        timeline_navigation.increase_speed_2x()
        _sleep_for(30)
        expected_video_sec, delta = _calculate_slide_and_delta(30, 0, 4)
        assert _recognize_and_find_expected_speed_in_interval(expected_video_sec, delta)

        timeline_navigation.pause_and_to_begin()
        timeline_navigation.play()
        timeline_navigation.increase_speed_2x()
        timeline_navigation.increase_speed_2x()
        timeline_navigation.increase_speed_2x()
        _sleep_for(20)
        expected_video_sec, delta = _calculate_slide_and_delta(20, 0, 8)
        assert _recognize_and_find_expected_speed_in_interval(expected_video_sec, delta)

        timeline_navigation.pause_and_to_begin()
        timeline_navigation.play()
        timeline_navigation.increase_speed_2x()
        timeline_navigation.increase_speed_2x()
        timeline_navigation.increase_speed_2x()
        timeline_navigation.increase_speed_2x()
        _sleep_for(20)
        expected_video_sec, delta = _calculate_slide_and_delta(20, 0, 16)
        assert _recognize_and_find_expected_speed_in_interval(expected_video_sec, delta)

        # Backward
        # Opening new camera each time is the easiest way to manipulate backward playback speed
        rtree = ResourceTree(testkit_api, hid)
        camera_scene_item_1 = rtree.get_camera(test_camera_1.name).open_in_new_tab()
        camera_scene_item_1.wait_for_accessible()
        timeline_navigation.to_beginning()
        timeline_navigation.play()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.to_beginning()
        _sleep_for(60)
        expected_video_sec, delta = _calculate_slide_and_delta(60, 480, -1)
        assert _recognize_and_find_expected_speed_in_interval(expected_video_sec, delta)

        camera_scene_item_2 = rtree.get_camera(test_camera_1.name).open_in_new_tab()
        camera_scene_item_2.wait_for_accessible()
        timeline_navigation.to_beginning()
        timeline_navigation.play()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.to_beginning()
        _sleep_for(30)
        expected_video_sec, delta = _calculate_slide_and_delta(30, 480, -2)
        assert _recognize_and_find_expected_speed_in_interval(expected_video_sec, delta)

        camera_scene_item_3 = rtree.get_camera(test_camera_1.name).open_in_new_tab()
        camera_scene_item_3.wait_for_accessible()
        timeline_navigation.to_beginning()
        timeline_navigation.play()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.to_beginning()
        _sleep_for(30)
        expected_video_sec, delta = _calculate_slide_and_delta(30, 480, -4)
        assert _recognize_and_find_expected_speed_in_interval(expected_video_sec, delta)

        camera_scene_item_4 = rtree.get_camera(test_camera_1.name).open_in_new_tab()
        camera_scene_item_4.wait_for_accessible()
        timeline_navigation.to_beginning()
        timeline_navigation.play()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.to_beginning()
        _sleep_for(30)
        expected_video_sec, delta = _calculate_slide_and_delta(30, 480, -8)
        assert _recognize_and_find_expected_speed_in_interval(expected_video_sec, delta)

        camera_scene_item_5 = rtree.get_camera(test_camera_1.name).open_in_new_tab()
        camera_scene_item_5.wait_for_accessible()
        timeline_navigation.to_beginning()
        timeline_navigation.play()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.lower_speed_2x()
        timeline_navigation.to_beginning()
        _sleep_for(25)
        expected_video_sec, delta = _calculate_slide_and_delta(25, 480, -16)
        assert _recognize_and_find_expected_speed_in_interval(expected_video_sec, delta)


def _calculate_slide_and_delta(measuring_time: int, starting_number: int, expected_speed: int):
    # Allow actual speed to deviate 15% from expected
    deviation = 0.15
    expected_video_sec = starting_number + expected_speed * measuring_time
    delta = expected_speed * measuring_time * deviation
    return expected_video_sec, delta


if __name__ == '__main__':
    exit(test_playback_speed().main())
