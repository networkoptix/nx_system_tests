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


class test_NVR_license_manual_activation(VMSTest):
    """NVR license can be activated on PC.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/83654

    Selection-Tag: 83654
    Selection-Tag: licenses
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        server_vm.api.set_license_server(license_server.url())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        main_menu = MainMenu(testkit_api, hid)
        hwid = main_menu.activate_system_administration().get_hwid()
        last_received_license = license_server.generate({
            'BRAND2': server_vm.api.get_brand(),
            'CLASS2': 'nvr',
            'QUANTITY2': 1,
            })
        content = license_server.activate(last_received_license, hwid)
        manual_activation_file_path = client_installation.temp_dir() / 'manual_activation_83654_1.txt'
        if manual_activation_file_path.exists():
            manual_activation_file_path.unlink()
        manual_activation_file_path.write_text(content)
        system_administration_dialog = main_menu.activate_system_administration()
        system_administration_dialog.open_tab('Licenses')
        system_administration_dialog.licenses_tab.set_activation_tab('Manual Activation'.title())
        system_administration_dialog.licenses_tab.activate_manually(client_installation.temp_dir() / 'manual_activation_83654_1.txt')
        [license_data] = system_administration_dialog.licenses_tab.get_license_data()
        assert license_data.license_type == 'NVR'

        system_administration_dialog.licenses_tab.set_activation_tab('Internet Activation'.title())
        last_received_license = license_server.generate({
            'BRAND2': server_vm.api.get_brand(),
            'CLASS2': 'nvr',
            'QUANTITY2': 1,
            })
        _, error_text = system_administration_dialog.licenses_tab.activate_license(last_received_license)
        message_dialog_1 = MessageBox(testkit_api, hid)
        assert message_dialog_1.wait_until_appears(20).get_title() == 'Failed to activate license'
        message_dialog_1.close_by_button('OK')
        assert system_administration_dialog.licenses_tab.get_row_count() == 1

        content1 = license_server.activate(last_received_license, hwid)
        path = client_installation.temp_dir() / 'manual_activation_83654_2.txt'
        if path.exists():
            path.unlink()
        path.write_text(content1)
        system_administration_dialog.licenses_tab.set_activation_tab('Manual Activation'.title())
        system_administration_dialog.licenses_tab.activate_manually(client_installation.temp_dir() / 'manual_activation_83654_2.txt')
        message_dialog_2 = MessageBox(testkit_api, hid)
        assert message_dialog_2.wait_until_appears(20).get_title() == 'Failed to activate license'
        message_dialog_2.close_by_button('OK')
        assert system_administration_dialog.licenses_tab.get_row_count() == 1


if __name__ == '__main__':
    exit(test_NVR_license_manual_activation().main())
