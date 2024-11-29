# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.server_login_steps import _log_in_using_main_menu
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_admin_cannot_deactivate_license(VMSTest):
    """Admin can not deactivate license.

    Create user with role Administrator, log in as administrator, open Licenses tab in
    System Administration, select some purchase license, check Deactivate button does not appear.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/15819

    Selection-Tag: 15819
    Selection-Tag: licenses
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        server_vm.allow_license_server_access(license_server.url())
        server_vm.api.set_license_server(license_server.url())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        server_vm.api.activate_license(license_server.generate({
            'QUANTITY2': 1,
            'BRAND2': server_vm.api.get_brand(),
            }))
        server_vm.api.add_local_admin('administrator', 'WellKnownPassword2')
        address_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        _log_in_using_main_menu(testkit_api, hid, address_port, 'administrator', 'WellKnownPassword2')
        system_administration_dialog = MainMenu(testkit_api, hid).activate_system_administration()
        system_administration_dialog.open_tab('Licenses')
        system_administration_dialog.licenses_tab.select_single_license()
        assert not system_administration_dialog.licenses_tab.deactivate_button_is_accessible()


if __name__ == '__main__':
    exit(test_admin_cannot_deactivate_license().main())
