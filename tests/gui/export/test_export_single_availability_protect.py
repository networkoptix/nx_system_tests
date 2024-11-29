# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_export_single_availability_protect(VMSTest):
    """Availability of Protect with password option.

    Open single tab of export dialog, check password protection is unavailable for mkv,
    avi and mp4 extensions, password protection is available for nov and exe, protection checkbox
    is not set by default.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47278

    Selection-Tag: 47278
    Selection-Tag: export
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        [test_camera_1] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file='samples/time_test_video.mp4',
            )
        testkit_api, _ = start_desktop_client_with_camera_open(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation, server_vm, test_camera_1.name)
        hid = HID(testkit_api)
        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.2)
        export_settings.exporter().set_extension('mkv')
        assert not export_settings.settings().is_protection_available()
        export_settings.exporter().set_extension('avi')
        assert not export_settings.settings().is_protection_available()
        export_settings.exporter().set_extension('mp4')
        assert not export_settings.settings().is_protection_available()
        export_settings.exporter().set_extension('nov')
        assert export_settings.settings().is_protection_available()
        assert not export_settings.settings().is_protection_set()
        export_settings.exporter().set_extension('exe')
        assert export_settings.settings().is_protection_available()
        assert not export_settings.settings().is_protection_set()


if __name__ == '__main__':
    exit(test_export_single_availability_protect().main())
