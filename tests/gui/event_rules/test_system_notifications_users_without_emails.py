# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from distrib import BranchNotSupported
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.local_settings import LocalSettingsDialog
from gui.desktop_ui.dialogs.user_settings import UserSettingsDialog
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.right_panel_widget.notifications_ribbon import NotificationsRibbon
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_system_notifications_users_without_emails(VMSTest):
    """System notifications and Some users have not set their email addresses.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/1267

    Selection-Tag: 1267
    Selection-Tag: event_rules
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            raise BranchNotSupported("Test should be fixed for VMS 6.1+")

        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        server_vm.api.add_local_live_viewer('Test', 'WellKnownPassword2')
        server_vm.api.add_local_live_viewer('live', 'WellKnownPassword2')
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        MainMenu(testkit_api, hid).open_local_settings_dialog()
        local_settings_dialog = LocalSettingsDialog(testkit_api, hid)
        # TODO: Need to fix in VMS 6.1+
        local_settings_dialog.activate_tab("Notifications")
        local_settings_dialog.notifications_tab.set_checkbox_by_text('Some users have not set their email addresses', True)
        local_settings_dialog.save()
        notifications_ribbon = NotificationsRibbon(testkit_api, hid)
        tile1 = notifications_ribbon.get_tile_by_name('Email address is not set for 2 users')
        assert tile1 is not None
        assert _get_tile_text(tile1) == 'live\nTest'
        tile = notifications_ribbon.get_tile_by_name('Email address is not set for 2 users')
        assert tile is not None
        notification = tile.get_label_by_name('nameLabel')
        if notification is not None:
            hid.mouse_left_click_on_object(notification)
        user_settings_dialog = UserSettingsDialog(testkit_api, hid)
        general_tab = user_settings_dialog.select_general_tab()
        assert general_tab.get_login() == 'live'
        general_tab.set_email('email@email.com')
        user_settings_dialog.save_and_close()
        tile2 = notifications_ribbon.get_tile_by_name('Email address is not set for 1 user')
        assert tile2 is not None
        assert _get_tile_text(tile2) == 'Test'


def _get_tile_text(tile):
    tile_text = tile.get_label_by_name('resourceListLabel').get_text()
    tile_text = tile_text.replace('<b>', '').replace('</b>', '').replace('<br/>', '\n')
    return tile_text


if __name__ == '__main__':
    exit(test_system_notifications_users_without_emails().main())
