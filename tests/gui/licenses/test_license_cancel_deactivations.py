# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.messages import MessageBox
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_license_cancel_deactivations(VMSTest):
    """License cancel deactivation.

    Note the quantity of remaining deactivations of the license, start deactivation and cancel it,
    check quantity of deactivations is not reduced.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/67029

    Selection-Tag: 67029
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
        system_administration_dialog = MainMenu(testkit_api, hid).activate_system_administration()
        system_administration_dialog.open_tab('licenses')
        system_administration_dialog.licenses_tab.open_details_of_single_license()
        open_license_tab = system_administration_dialog.licenses_tab
        deactivations = open_license_tab.get_deactivations_in_details()
        system_administration_dialog.licenses_tab.close_details()
        license_code = system_administration_dialog.licenses_tab.get_single_code()
        system_administration_dialog.licenses_tab.select_single_license()
        system_administration_dialog.licenses_tab.open_deactivation_form()
        system_administration_dialog.licenses_tab.fill_deactivation_form()
        expected_message = ' '.join([deactivations, 'deactivations remaining'])
        full_text = system_administration_dialog.licenses_tab.get_deactivation_error().get_text()
        assert expected_message in full_text

        MessageBox(testkit_api, hid).close_by_button('Cancel')
        [license_data] = system_administration_dialog.licenses_tab.get_license_data()
        assert license_data.license_key == license_code

        system_administration_dialog.licenses_tab.open_details_of_single_license()
        assert system_administration_dialog.licenses_tab.get_deactivations_in_details() == deactivations


if __name__ == '__main__':
    exit(test_license_cancel_deactivations().main())
