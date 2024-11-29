# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.videowalls import VideowallCreationDialog
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_create_videowall(VMSTest):
    """Create videowall.

    Create videowall and check that it appeared in resource tree
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/767

    Selection-Tag: 767
    Selection-Tag: videowalls
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        server_vm.allow_license_server_access(license_server.url())
        server_vm.api.set_license_server(license_server.url())
        server_vm.api.activate_license(license_server.generate({
            'CLASS2': 'videowall',
            'QUANTITY2': 1,
            'BRAND2': server_vm.api.get_brand(),
            }))
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        with VideowallCreationDialog(testkit_api, hid, close_by='Cancel') as videowall_dialog_1:
            assert videowall_dialog_1.ok_button_is_active()
        with VideowallCreationDialog(testkit_api, hid) as videowall_dialog_2:
            videowall_dialog_2.insert_name('')
            assert not videowall_dialog_2.ok_button_is_active()
            videowall_dialog_2.insert_name('Test video wall')
        assert ResourceTree(testkit_api, hid).has_videowall('Test video wall')


if __name__ == '__main__':
    exit(test_create_videowall().main())
