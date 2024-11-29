# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.messages import AboutDialog
from gui.desktop_ui.messages import MessageBox
from gui.gui_test_stand import GuiTestStand
from gui.server_login_steps import _log_in_to_server
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.merging import merge_systems
from tests.base_test import VMSTest


class test_license_offline_server_and_permanent_license(VMSTest):
    """C67023 License offline server and permanent license.

    Merge two servers into one system, activate license at the one of them,
    connect to this server and check About contains info about license company,
    connect to the other server and check About contains info about license company,
    stop server with the license, check license has status "Error".
    Open license details for new activated permanent license on online server,
    check that string 'Deactivations Remaining: 3' is present in license details form.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65843
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/67023

    Selection-Tag: 65843
    Selection-Tag: 67023
    Selection-Tag: licenses
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, server_vm2, client_installation] = exit_stack.enter_context(machine_pool.setup_two_servers_client())
        server_vm.allow_license_server_access(license_server.url())
        server_vm.api.set_license_server(license_server.url())
        server_vm2.allow_license_server_access(license_server.url())
        server_vm2.api.set_license_server(license_server.url())
        merge_systems(server_vm, server_vm2, take_remote_settings=False)
        server_vm2.api.activate_license(license_server.generate({
            'BRAND2': server_vm2.api.get_brand(),
            'COMPANY2': 'Network Optix',
            }))
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm2),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm2,
            )
        hid = HID(testkit_api)
        main_menu = MainMenu(testkit_api, hid)
        system_administration = main_menu.activate_system_administration()
        system_administration.open_tab('licenses')
        licenses_tab = system_administration.licenses_tab
        licenses_tab.license_table.wait_for_accessible()
        licenses_tab.open_details_of_single_license()
        assert licenses_tab.get_deactivations_in_details() == '3'
        licenses_tab.close_details()

        about_dialog = AboutDialog.open_by_f1(testkit_api, hid)
        assert about_dialog.has_license_and_support_field()
        assert about_dialog.has_support_text('https://support.networkoptix.com')
        about_dialog.close()
        system_administration.close()

        address_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        _log_in_to_server(testkit_api, hid, address_port, server_vm)
        server_vm2.stop()
        message_dialog = MessageBox(testkit_api, hid)
        if message_dialog.is_accessible_timeout(2):
            message_dialog.wait_until_closed()
        about_dialog = AboutDialog.open_by_f1(testkit_api, hid)
        assert about_dialog.has_license_and_support_field()
        assert about_dialog.has_support_text('https://support.networkoptix.com')

        about_dialog.close()
        system_administration = main_menu.activate_system_administration()
        system_administration.open_tab('licenses')
        licenses_tab = system_administration.licenses_tab
        [license_data] = licenses_tab.get_license_data()
        assert license_data.status == 'Error'
        assert license_data.server == 'Server not found'

        licenses_tab.select_by_status(status='Error')
        hid.mouse_left_click_on_object(licenses_tab.get_remove_button())
        licenses_tab.license_table.wait_for_inaccessible()
        about_dialog = AboutDialog.open_by_f1(testkit_api, hid)
        assert not about_dialog.has_license_and_support_field()


if __name__ == '__main__':
    exit(test_license_offline_server_and_permanent_license().main())
