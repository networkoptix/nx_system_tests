# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.ocr import ImageDigitsRecognition
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import Timeline
from gui.desktop_ui.timeline import TimelineNavigation
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_3_seconds_local_video(VMSTest):
    """Last 3 seconds for local video.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1887

    Selection-Tag: 1887
    Selection-Tag: camera_playback
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
        remote_path = gui_prerequisite_supplier.upload_to_remote('test1887/20sec.mp4', client_installation.os_access)
        MainMenu(testkit_api, hid).open_local_settings_dialog().add_folder(remote_path.parent)
        ResourceTree(testkit_api, hid).wait_for_any_local_file()
        ResourceTree(testkit_api, hid).get_local_file('20sec.mp4').open()
        TimelineNavigation(testkit_api, hid).pause()
        # Position of last 3 seconds for 20-seconds archive.
        Timeline(testkit_api, hid).click_at_offset(0.95)
        time.sleep(2)
        # Checking that slider does not skip.
        capture = Scene(testkit_api, hid).items_visually_ordered()[0].image_capture()
        ImageDigitsRecognition(capture).has_in_delta_neighborhood(19, 2)


if __name__ == '__main__':
    exit(test_3_seconds_local_video().main())
