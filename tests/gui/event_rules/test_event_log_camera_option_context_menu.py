# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from distrib import BranchNotSupported
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.camera_settings import CameraSettingsDialog
from gui.desktop_ui.event_rules import get_event_rules_dialog
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_event_log_camera_option_context_menu(VMSTest):
    """Camera option via context menu.

    Connect camera to server and disconnect it to get a network issue. Open event log and initiate
    all available camera-related actions from context menu for the camera.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1407

    Selection-Tag: 1407
    Selection-Tag: event_rules
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            raise BranchNotSupported("Test should be fixed for VMS 6.1+")

        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        # same video for multiple cameras
        with playing_testcamera(machine_pool, server_vm.os_access, 'samples/dynamic_test_video.mp4'):
            [test_camera_1] = server_vm.api.add_test_cameras(0, 1)
            ResourceTree(testkit_api, hid).wait_for_cameras([test_camera_1.name])
        event_log = MainMenu(testkit_api, hid).activate_system_administration().open_event_log()
        event_log.activate_source_context_menu(test_camera_1.name, 'Camera Settings...')
        with CameraSettingsDialog(testkit_api, hid) as camera_settings:
            camera_settings.wait_until_appears()

        event_log.activate_source_context_menu(test_camera_1.name, 'Check Camera Issues...')
        # TODO: Need to fix in VMS 6.1+
        assert event_log.get_event_filter().current_item() == 'Any Camera Issue'
        assert event_log.get_device_filter().get_text() == test_camera_1.name
        assert event_log.get_action_filter().current_item() == 'Write to log'
        assert event_log.has_event_with_source_and_action('Network Issue', test_camera_1.name, 'Write to log')

        event_log.activate_source_context_menu(test_camera_1.name, 'Camera Rules...')
        window = get_event_rules_dialog(testkit_api, hid)
        camera_id_from_search_field = window.get_search_field().get_text()
        assert camera_id_from_search_field == str(test_camera_1.id)


if __name__ == '__main__':
    exit(test_event_log_camera_option_context_menu().main())
