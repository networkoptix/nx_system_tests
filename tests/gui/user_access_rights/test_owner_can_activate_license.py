# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_owner_can_activate_license(VMSTest):
    """Owner can activate license.

    # https://networkoptix.testrail.net/index.php?/cases/view/122087
    # https://networkoptix.testrail.net/index.php?/cases/view/686

    Selection-Tag: 122087
    Selection-Tag: 686
    Selection-Tag: licenses
    Selection-Tag: users_and_group_management
    Selection-Tag: gui-smoke-test
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
        channels_count = 4
        license_key = license_server.generate({
            'QUANTITY2': channels_count,
            'BRAND2': server_vm.api.get_brand(),
            })
        system_administration_dialog.licenses_tab.activate_license(license_key)
        [license_data] = system_administration_dialog.licenses_tab.get_license_data()
        assert license_data.license_type == 'Professional'
        assert license_data.channels == str(channels_count)
        assert license_data.expires == 'Never'


if __name__ == '__main__':
    exit(test_owner_can_activate_license().main())
