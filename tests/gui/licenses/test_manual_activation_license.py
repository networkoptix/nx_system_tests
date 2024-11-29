# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.messages import AboutDialog
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_manual_activation_license(VMSTest):
    """Manual activation license.

    Activate a license manually with prepared file, check regional data of the license in About form.
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65845

    Selection-Tag: 65845
    Selection-Tag: licenses
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
        system_administration_dialog = MainMenu(testkit_api, hid).activate_system_administration()
        system_administration_dialog.open_tab('Licenses')
        licenses_tab = system_administration_dialog.licenses_tab
        licenses_tab.set_activation_tab("Manual Activation")
        last_received_license = license_server.generate({'BRAND2': server_vm.api.get_brand()})
        content = license_server.activate(last_received_license, licenses_tab.get_hwid())
        manual_activation_file_path = client_installation.temp_dir() / 'manual_activation_65845.txt'
        if manual_activation_file_path.exists():
            manual_activation_file_path.unlink()
        manual_activation_file_path.write_text(content)
        licenses_tab.activate_manually(manual_activation_file_path)
        about_dialog = AboutDialog.open_by_f1(testkit_api, hid)
        assert about_dialog.has_license_and_support_field()
        assert about_dialog.has_support_text('https://support.networkoptix.com')


if __name__ == '__main__':
    exit(test_manual_activation_license().main())
