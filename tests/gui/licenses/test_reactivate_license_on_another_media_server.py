# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.messages import MessageBox
from gui.gui_test_stand import GuiTestStand
from gui.server_login_steps import _log_in_to_server
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_reactivate_license_on_another_media_server(VMSTest):
    """Reactivate license on another media server.

    Deactivate license at the first media server, check this license is absent,
    activate the same license at the second media server, check the license is activated.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/15820

    Selection-Tag: 15820
    Selection-Tag: licenses
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
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm2),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm2,
            )
        hid = HID(testkit_api)
        main_menu = MainMenu(testkit_api, hid)
        server_vm2.api.activate_license(license_server.generate({
            'QUANTITY2': 1,
            'BRAND2': server_vm2.api.get_brand(),
            }))
        system_administration_dialog_1 = main_menu.activate_system_administration()
        system_administration_dialog_1.open_tab('licenses')
        system_administration_dialog_1.licenses_tab.open_details_of_single_license()
        open_license_tab = system_administration_dialog_1.licenses_tab
        deactivations = open_license_tab.get_deactivations_in_details()
        if deactivations == '0':
            raise RuntimeError("Impossible to deactivate the license.")

        system_administration_dialog_1.licenses_tab.close_details()
        license_code = system_administration_dialog_1.licenses_tab.get_single_code()
        system_administration_dialog_1.licenses_tab.select_single_license()
        system_administration_dialog_1.licenses_tab.open_deactivation_form()
        system_administration_dialog_1.licenses_tab.fill_deactivation_form()
        system_administration_dialog_1.licenses_tab.confirm_deactivation()
        MessageBox(testkit_api, hid).close_by_button('OK')
        assert not system_administration_dialog_1.licenses_tab.get_license_data()

        system_administration_dialog_1.save_and_close()
        main_menu.disconnect_from_server()
        address_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        _log_in_to_server(testkit_api, hid, address_port, server_vm)
        system_administration_dialog_2 = main_menu.activate_system_administration()
        system_administration_dialog_2.open_tab('licenses')
        system_administration_dialog_2.licenses_tab.activate_license(license_code)
        [license_data] = system_administration_dialog_2.licenses_tab.get_license_data()
        assert license_data.license_key == license_code


if __name__ == '__main__':
    exit(test_reactivate_license_on_another_media_server().main())
