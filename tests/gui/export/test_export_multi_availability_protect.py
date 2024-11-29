# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.timeline import Timeline
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import testcameras_with_just_recorded_archive
from tests.base_test import VMSTest


class test_export_multi_availability_protect(VMSTest):
    """Availability of Protect with password option.

    Check password protection option is available for multi tab of export dialog
    for nov and exe extensions.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/47281

    Selection-Tag: 47281
    Selection-Tag: export
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
        [test_camera_1, test_camera_2] = testcameras_with_just_recorded_archive(
            nx_server=server_vm,
            video_file='samples/time_test_video.mp4',
            camera_count=2,
            )
        camera_names = [test_camera_1.name, test_camera_2.name]
        ResourceTree(testkit_api, hid).select_cameras(camera_names).open_by_context_menu()
        Scene(testkit_api, hid).wait_for_items_number(len(camera_names))
        export_settings = Timeline(testkit_api, hid).open_export_video_dialog_for_interval(0, 0.2)
        export_settings.select_tab('Multi Video')
        export_settings.exporter().set_extension('nov')
        assert export_settings.settings().is_protection_available()
        export_settings.exporter().set_extension('exe')
        assert export_settings.settings().is_protection_available()


if __name__ == '__main__':
    exit(test_export_multi_availability_protect().main())
