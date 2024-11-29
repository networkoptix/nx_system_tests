# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.messages import ProgressDialog
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_export_empty_password(VMSTest):
    """Error is displayed if password input is left empty.

    Check export is not started for password protection option with empty password text field,
    check correct error message about that.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47291

    Selection-Tag: 47291
    Selection-Tag: export
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        video_file = 'samples/time_test_video.mp4'
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, video_file))
        [test_camera_1] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file=video_file,
            )
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.2)
        export_settings.exporter().set_extension('nov')
        export_settings.settings().set_password(password='')
        export_settings.exporter().click_export_button()
        assert export_settings.settings().password_error_text() == 'Please enter the password.'
        assert not ProgressDialog(testkit_api).is_open()


if __name__ == '__main__':
    exit(test_export_empty_password().main())
