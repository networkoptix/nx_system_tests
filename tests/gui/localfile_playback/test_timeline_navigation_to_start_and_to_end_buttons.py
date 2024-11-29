# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from datetime import datetime
from datetime import timedelta

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import TimelineNavigation
from gui.desktop_ui.timeline import TimelineTooltip
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest

_logger = logging.getLogger(__name__)


class test_timeline_navigation_to_start_and_to_end_buttons(VMSTest):
    """Go to beginning and end by buttons.

    Open local video, pause the video, play the video.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1948

    Selection-Tag: 1948
    Selection-Tag: localfile_playback
    Selection-Tag: timeline_and_controls
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        remote_path = gui_prerequisite_supplier.upload_to_remote('localfiles/video_sound.mkv', client_installation.os_access)
        MainMenu(testkit_api, hid).open_local_settings_dialog().add_folder(remote_path.parent)
        ResourceTree(testkit_api, hid).wait_for_any_local_file()
        ResourceTree(testkit_api, hid).get_local_file('video_sound.mkv').open()
        timeline_navigation = TimelineNavigation(testkit_api, hid)
        timeline_navigation.to_end()
        time.sleep(.5)
        expected_time = datetime.strptime('00:00', '%M:%S')
        timeline_tooltip = TimelineTooltip(testkit_api)
        actual_time = timeline_tooltip.time('%M:%S')
        _logger.info('Actual TimelineTooltip timestamp is %s', actual_time)
        assert abs(actual_time - expected_time) <= timedelta(seconds=3)

        timeline_navigation.to_beginning()
        time.sleep(.5)
        actual_time = timeline_tooltip.time('%M:%S')
        _logger.info('Actual TimelineTooltip timestamp is %s', actual_time)
        assert abs(actual_time - expected_time) <= timedelta(seconds=3)


if __name__ == '__main__':
    exit(test_timeline_navigation_to_start_and_to_end_buttons().main())
