# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from distrib import BranchNotSupported
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.server_settings import ServerSettingsDialog
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.right_panel_widget.notifications_ribbon import NotificationsRibbon
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import playing_testcamera
from tests.base_test import VMSTest


class test_storages_are_not_configured(VMSTest):
    """Storages are not configured.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1271

    Selection-Tag: 1271
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
        exit_stack.enter_context(playing_testcamera(machine_pool, server_vm.os_access, 'samples/dynamic_test_video.mp4'))
        server_api = server_vm.api
        [test_camera_1] = server_api.add_test_cameras(0, 1)
        server_api.start_recording(test_camera_1.id)
        with ResourceTree(testkit_api, hid).get_server(server_api.get_server_name()).open_settings() as server_settings:
            server_settings.open_storage_management_tab()
            for storage in server_settings.storage_management_tab.list_storages():
                storage.disable()

        notifications_ribbon = NotificationsRibbon(testkit_api, hid)
        # TODO: Need to fix in VMS 6.1+
        notifications_ribbon.wait_for_notification('Storage is not configured', timeout_sec=60)
        tile = notifications_ribbon.get_tile_by_name('Storage is not configured')
        assert tile is not None
        notification = tile.get_label_by_name('nameLabel')
        if notification is not None:
            hid.mouse_left_click_on_object(notification)
        with ServerSettingsDialog(testkit_api, hid) as server_settings:
            assert server_settings.is_open()
            added_storage = str(server_vm.default_archive_dir)
            server_settings.storage_management_tab.get_storage(added_storage).enable()
        notifications_ribbon.wait_for_notification_disappear('Storage is not configured', timeout_sec=60)


if __name__ == '__main__':
    exit(test_storages_are_not_configured().main())
