# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_camera_archive_preview_period(VMSTest):
    """Camera archive preview period.

    Activate preview search for archive, verify intervals length, navigation and further search in
    interval

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1516

    Selection-Tag: unstable
    Selection-Tag: 1516
    Selection-Tag: camera_playback
    """

    # TODO: fix unstable: SQ-768
    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        camera_archive = server_vm.default_archive().camera_archive(test_camera_1.physical_id)
        duration_sec = int(timedelta(days=5).total_seconds())
        camera_archive.high().add_fake_record(
            start_time=datetime.now(timezone.utc) - timedelta(seconds=duration_sec * 2),
            duration_sec=duration_sec,
            bitrate_bps=8,
            chunk_duration_sec=duration_sec,  # TODO: Investigate why we record a huge single chunk
            )
        server_vm.api.rebuild_main_archive()
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        timeline = Timeline(testkit_api, hid)
        timeline.open_preview_search_for_interval(0.0, 0.9)
        # 5 days, 11 items expected - each item is for half-day.
        # In rare case when search is activated at strictly 12:00AM there can be only 10 items
        # SQ-768
        scene = Scene(testkit_api, hid)
        scene.wait_for_items_number(11)
        timeline.verify_preview_search_period(timedelta(hours=12), 5)

        # first item for first period may have archive not through all its duration
        # so select 2nd item, archive exists for the whole period
        scene.items_visually_ordered()[2].click()
        timeline.open_preview_search()
        scene.wait_for_items_number(12)
        timeline.verify_preview_search_period(timedelta(hours=1), 5)

        timeline.open_preview_search()
        scene.wait_for_items_number(12)
        timeline.verify_preview_search_period(timedelta(minutes=5), 5)

        timeline.open_preview_search()
        scene.wait_for_items_number(10)
        timeline.verify_preview_search_period(timedelta(seconds=30), 5)

        timeline.open_preview_search()
        scene.wait_for_items_number(3)
        timeline.verify_preview_search_period(timedelta(seconds=10), 5)

        timeline.open_preview_search()
        message_box = MessageBox(testkit_api, hid).wait_until_appears()
        preview_search_expected_text = (
            'Cannot perform Preview Search. '
            'Please select a period of 15 seconds or longer.')
        assert message_box.get_title() == 'Too short period selected'
        assert preview_search_expected_text in message_box.get_labels()


if __name__ == '__main__':
    exit(test_camera_archive_preview_period().main())
