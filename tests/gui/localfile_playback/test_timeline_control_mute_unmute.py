# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import TimelineControlWidget
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_timeline_control_mute_unmute(VMSTest):
    """Buttons mute and unmute.

    Open local video, click mute button, click mute button again.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1914

    Selection-Tag: 1914
    Selection-Tag: localfile_playback
    Selection-Tag: timeline_and_controls
    Selection-Tag: gui-smoke-test
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
        timeline_control_widget = TimelineControlWidget(testkit_api, hid)
        timeline_control_widget.mute_button.set(True)
        time.sleep(1)
        assert timeline_control_widget.volume_slider.is_muted()
        assert timeline_control_widget.mute_button.is_checked()
        timeline_control_widget.mute_button.set(False)
        assert not timeline_control_widget.volume_slider.is_muted()
        assert not timeline_control_widget.mute_button.is_checked()


if __name__ == '__main__':
    exit(test_timeline_control_mute_unmute().main())
