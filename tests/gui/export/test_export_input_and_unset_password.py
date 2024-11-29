# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_with_camera_open
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_export_input_and_unset_password(VMSTest):
    """If Protect with password was unset and exported file is open without password.

    Open export dialog, choose nov format, set password protection and input any password,
    then unset password protection and export the file, check exported file is not protected.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47290

    Selection-Tag: 47290
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
        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.3)
        export_settings.exporter().set_extension('nov')
        export_settings.single_camera_settings.set_password('123456')
        export_settings.single_camera_settings.unset_password()
        export_settings.export_with_specific_path(client_installation.temp_dir() / 'temp_47290.nov')
        local_file_node = ResourceTree(testkit_api, hid).wait_for_local_file('temp_47290.nov')
        assert local_file_node.is_insecure_multi_export()
        assert local_file_node.has_video_item(test_camera_1.name)


if __name__ == '__main__':
    exit(test_export_input_and_unset_password().main())
