# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_timeline_panel(VMSTest):
    """Timeline panel.

    C914:
    Open camera after desktop client restart, check default timeline panel status,
    check hide and show panel, check saving of the setting for new tabs.

    C915:
    Check enabled buttons for live stream and for archive playback.

    C916:
    Check enabled buttons for live stream paused and for archive playback paused.

    # https://networkoptix.testrail.net/index.php?/cases/view/914
    # https://networkoptix.testrail.net/index.php?/cases/view/915
    # https://networkoptix.testrail.net/index.php?/cases/view/916

    Selection-Tag: 914
    Selection-Tag: 915
    Selection-Tag: 916
    Selection-Tag: timeline_and_controls
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/time_test_video.mp4', 2))
        # Two cameras with/without recording have different state of timeline buttons,
        # which are tested in these test cases.
        # This is different from the C915, C916 test cases which instruct to have only one camera.
        # The second camera is recording archive while the first is tested.
        [test_camera_live, test_camera_recorded] = server_vm.api.add_test_cameras(0, 2)
        server_vm.api.start_recording(test_camera_recorded.id)
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_live.name)
        hid = HID(testkit_api)
        timeline = Timeline(testkit_api, hid)
        timeline.show()
        assert timeline.is_open()
        rtree = ResourceTree(testkit_api, hid)
        live_camera_scene_item_1 = rtree.get_camera(test_camera_live.name).open_in_new_tab()
        live_camera_scene_item_1.wait_for_accessible()
        assert timeline.is_open()
        timeline.hide()
        assert not timeline.is_open()
        live_camera_scene_item_2 = rtree.get_camera(test_camera_live.name).open_in_new_tab()
        live_camera_scene_item_2.wait_for_accessible()
        assert not timeline.is_open()
        server_vm.api.stop_recording(test_camera_recorded.id)

        # C915
        timeline.show()
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        assert timeline_navigation.button_is_enabled('Pause')
        assert not timeline_navigation.button_is_enabled('Speed Down')
        assert not timeline_navigation.button_is_enabled('Previous Chunk')
        assert not timeline_navigation.button_is_enabled('Speed Up')
        assert not timeline_navigation.button_is_enabled('Next Chunk')
        # C916
        timeline_navigation.pause()
        assert timeline_navigation.button_is_enabled('Play')
        assert not timeline_navigation.button_is_enabled('Previous Frame')
        assert not timeline_navigation.button_is_enabled('Previous Chunk')
        assert not timeline_navigation.button_is_enabled('Next Frame')
        assert not timeline_navigation.button_is_enabled('Next Chunk')

        recorded_camera_scene_item = rtree.get_camera(test_camera_recorded.name).open_in_new_tab()
        recorded_camera_scene_item.wait_for_accessible()
        timeline.click_at_offset(0.1)

        # C916
        assert timeline_navigation.button_is_enabled('Play')
        assert timeline_navigation.button_is_enabled('Previous Frame')
        assert timeline_navigation.button_is_enabled('Previous Chunk')
        assert timeline_navigation.button_is_enabled('Next Frame')
        assert timeline_navigation.button_is_enabled('Next Chunk')
        # C915
        timeline_navigation.play()
        assert timeline_navigation.button_is_enabled('Pause')
        assert timeline_navigation.button_is_enabled('Speed Down')
        assert timeline_navigation.button_is_enabled('Previous Chunk')
        assert timeline_navigation.button_is_enabled('Speed Up')
        assert timeline_navigation.button_is_enabled('Next Chunk')


if __name__ == '__main__':
    exit(test_timeline_panel().main())
