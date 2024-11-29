# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.messages import AboutDialog
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_license_regional_support_in_about_form(VMSTest):
    """License regional support in about form.

    "Regional / License support" link is displayed on "About" dialog if License with filled company
    name was activated
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/65839

    Selection-Tag: 65839
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
        about_dialog = AboutDialog.open_by_f1(testkit_api, hid)
        assert about_dialog.has_license_and_support_field()
        assert about_dialog.has_support_text('https://support.networkoptix.com')


if __name__ == '__main__':
    exit(test_license_regional_support_in_about_form().main())
