# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.messages import MessageBox
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest

_logger = logging.getLogger(__name__)


class test_license_deactivation_with_multiselection(VMSTest):
    """License deactivation with multiselection.

    Activate two licenses, with 0 remaining deactivations and with possibility
    to deactivate one more, select both of them, fill the form and cancel deactivation
    at the alert form, check the both licenses are present in licenses list;
    select the both and deactivate them, confirm deactivation at the alert form,
    check only one license is present in licenses list, that is exactly license
    with 0 remaining deactivations.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/67028

    Selection-Tag: 67028
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
        server_vm.api.activate_license(license_server.generate({
            'QUANTITY2': 1,
            'BRAND2': server_vm.api.get_brand(),
            }))
        system_administration_dialog = MainMenu(testkit_api, hid).activate_system_administration()
        system_administration_dialog.open_tab('licenses')
        license_code = system_administration_dialog.licenses_tab.get_single_code()
        license_server.deactivate(license_code)
        server_vm.api.activate_license(license_code)
        license_server.deactivate(license_code)
        server_vm.api.activate_license(license_code)
        license_server.deactivate(license_code)
        server_vm.api.activate_license(license_code)
        codes_list = system_administration_dialog.licenses_tab.get_all_codes()
        system_administration_dialog.licenses_tab.select_all()
        system_administration_dialog.licenses_tab.open_deactivation_form()
        system_administration_dialog.licenses_tab.fill_deactivation_form()
        for code in codes_list:
            assert code in system_administration_dialog.licenses_tab.get_deactivation_error().get_text()

        system_administration_dialog.licenses_tab.confirm_deactivation()
        MessageBox(testkit_api, hid).wait_until_has_label('1 of 2 licenses cannot be deactivated', timeout=5)

        alert_message = system_administration_dialog.licenses_tab.get_deactivation_error().get_text()
        hid.mouse_left_click_on_object(system_administration_dialog.licenses_tab.get_deactivation_error_copy_button())
        MessageBox(testkit_api, hid).close_by_button('Cancel')
        assert system_administration_dialog.licenses_tab.get_row_count() == 2

        system_administration_dialog.licenses_tab.open_deactivation_form()
        system_administration_dialog.licenses_tab.fill_deactivation_form()
        system_administration_dialog.licenses_tab.confirm_deactivation()
        system_administration_dialog.licenses_tab.deactivate_other_licenses(1)
        MessageBox(testkit_api, hid).close_by_button('OK')
        assert system_administration_dialog.licenses_tab.get_row_count() == 1

        system_administration_dialog.licenses_tab.select_single_license()
        system_administration_dialog.licenses_tab.open_details_of_single_license()
        tab = system_administration_dialog.licenses_tab
        tab.get_deactivation_remaining_label().wait_for_accessible()
        assert tab.get_deactivations_in_details() == '0'
        open_license_tab = system_administration_dialog.licenses_tab
        assert open_license_tab.get_license_details_code_label().get_text() in alert_message


if __name__ == '__main__':
    exit(test_license_deactivation_with_multiselection().main())
