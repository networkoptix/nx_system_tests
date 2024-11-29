# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from datetime import datetime
from datetime import timedelta
from datetime import timezone

from _internal.service_registry import gui_prerequisite_store
from directories import get_run_dir
from doubles.video.ffprobe import SampleMediaFile
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_timeline_with_archive_chunks_display(VMSTest):
    """Check archive displayed properly on camera.

    # https://networkoptix.testrail.net/index.php?/cases/view/919

    Selection-Tag: 919
    Selection-Tag: timeline_and_controls
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4'))
        [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
        media_file = SampleMediaFile(gui_prerequisite_store.fetch('samples/overlay_test_video.mp4'))
        now = datetime.now(timezone.utc)
        camera_archive = server_vm.default_archive().camera_archive(test_camera_1.physical_id)
        camera_archive.save_media_sample(now - timedelta(hours=1), media_file)
        camera_archive.save_media_sample(now - timedelta(minutes=3), media_file)
        server_vm.api.rebuild_main_archive()
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        assert Timeline(testkit_api, hid).count_archive_chunks() == 2


if __name__ == '__main__':
    exit(test_timeline_with_archive_chunks_display().main())
