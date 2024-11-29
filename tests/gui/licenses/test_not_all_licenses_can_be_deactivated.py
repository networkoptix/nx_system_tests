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


class test_not_all_licenses_can_be_deactivated(VMSTest):
    """Not all licenses can be deactivated.

    Try to deactivate 3 licenses, one of them has 0 remaining deactivations, check 2 licenses are
    deactivated, but license with 0 deactivation is still present in licenses list.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/15839

    Selection-Tag: 15839
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
        system_administration_dialog = MainMenu(testkit_api, hid).activate_system_administration()
        system_administration_dialog.open_tab('licenses')
        server_vm.api.activate_license(license_server.generate({
            'CLASS2': 'edge',
            'QUANTITY2': 1,
            'BRAND2': server_vm.api.get_brand(),
            }))
        server_vm.api.activate_license(license_server.generate({
            'CLASS2': 'videowall',
            'QUANTITY2': 1,
            'BRAND2': server_vm.api.get_brand(),
            }))
        last_received_license = license_server.generate({'BRAND2': server_vm.api.get_brand()})
        _, error_text = system_administration_dialog.licenses_tab.activate_license(last_received_license)
        system_administration_dialog.licenses_tab.deactivate_license(last_received_license)
        system_administration_dialog.licenses_tab.activate_license(last_received_license)
        system_administration_dialog.licenses_tab.deactivate_license(last_received_license)
        system_administration_dialog.licenses_tab.activate_license(last_received_license)
        system_administration_dialog.licenses_tab.deactivate_license(last_received_license)
        system_administration_dialog.licenses_tab.activate_license(last_received_license)
        assert system_administration_dialog.licenses_tab.get_row_count() == 3

        system_administration_dialog.licenses_tab.select_all()
        system_administration_dialog.licenses_tab.open_deactivation_form()
        system_administration_dialog.licenses_tab.fill_deactivation_form()
        system_administration_dialog.licenses_tab.confirm_deactivation()
        MessageBox(testkit_api, hid).wait_until_has_label('1 of 3 licenses cannot be deactivated', timeout=5)

        system_administration_dialog.licenses_tab.deactivate_other_licenses(2)
        MessageBox(testkit_api, hid).close_by_button('OK')
        [license_data] = system_administration_dialog.licenses_tab.get_license_data()
        assert license_data.license_type == 'Professional'

        system_administration_dialog.licenses_tab.select_single_license()
        system_administration_dialog.licenses_tab.open_details_of_single_license()
        open_license_tab = system_administration_dialog.licenses_tab
        open_license_tab.get_deactivation_remaining_label().wait_for_accessible()
        assert open_license_tab.get_deactivations_in_details() == '0'


if __name__ == '__main__':
    exit(test_not_all_licenses_can_be_deactivated().main())
