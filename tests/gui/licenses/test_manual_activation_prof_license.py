# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_manual_activation_prof_license(VMSTest):
    """Activate professional license on PC.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/713

    Selection-Tag: 713
    Selection-Tag: licenses
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        main_menu = MainMenu(testkit_api, hid)
        hwid = main_menu.activate_system_administration().get_hwid()
        last_received_license = license_server.generate({'BRAND2': server_vm.api.get_brand()})
        content = license_server.activate(last_received_license, hwid)
        manual_activation_file_path = client_installation.temp_dir() / 'manual_activation_713.txt'
        if manual_activation_file_path.exists():
            manual_activation_file_path.unlink()
        manual_activation_file_path.write_text(content)
        system_administration_dialog = main_menu.activate_system_administration()
        system_administration_dialog.open_tab('Licenses')
        system_administration_dialog.licenses_tab.set_activation_tab('Manual Activation'.title())
        system_administration_dialog.licenses_tab.activate_manually(client_installation.temp_dir() / 'manual_activation_713.txt')
        [license_data] = system_administration_dialog.licenses_tab.get_license_data()
        assert license_data.license_type == 'Professional'
        assert license_data.status == 'OK'


if __name__ == '__main__':
    exit(test_manual_activation_prof_license().main())
