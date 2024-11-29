# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.system_administration import SystemAdministrationDialog
from gui.desktop_ui.right_panel_widget.notifications_ribbon import NotificationsRibbon
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_system_notifications_no_licenses(VMSTest):
    """System notifications and No Licenses.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1265

    Selection-Tag: 1265
    Selection-Tag: event_rules
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
        notifications_ribbon = NotificationsRibbon(testkit_api, hid)
        notifications_ribbon.wait_for_notification('No licenses')
        tile = notifications_ribbon.get_tile_by_name('No licenses')
        assert tile is not None, 'Tile "No licenses" was not found in notification ribbon'

        notification = tile.get_label_by_name('nameLabel')
        assert notification is not None, 'Failed to get notification "No licenses" as an object'

        hid.mouse_left_click_on_object(notification)
        assert SystemAdministrationDialog(testkit_api, hid).licenses_tab.is_open()


if __name__ == '__main__':
    exit(test_system_notifications_no_licenses().main())
