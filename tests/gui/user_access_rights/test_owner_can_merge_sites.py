# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.merge_systems import MergeSystemsDialog
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_owner_can_merge_sites(VMSTest):
    """Owner can merge sites.

    # https://networkoptix.testrail.net/index.php?/cases/view/115038

    Selection-Tag: 115038
    Selection-Tag: users_and_group_management
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        license_server = LocalLicenseServer()
        exit_stack.enter_context(license_server.serving())
        [server_vm_one, server_vm_two, client_installation] = exit_stack.enter_context(machine_pool.setup_two_servers_client())
        # Turn on auto discovery for test purposes. The second System|Site should be
        # in resource tree under the "Other systems" node.
        server_vm_two.api.set_system_settings({'autoDiscoveryEnabled': 'True'})
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm_one),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm_one,
            )
        hid = HID(testkit_api)
        server_vm_two_info = server_vm_two.api.get_server_info()
        resource_tree = ResourceTree(testkit_api, hid)
        other_site = resource_tree.wait_for_other_site(server_vm_two_info.site_name)
        pending_server = other_site.get_external_server(server_vm_two_info.server_name)
        # The word "System" is used in VMS 6.0. The word "Site" is used in newer versions.
        possible_actions = [
            'Merge to Currently Connected System...',
            'Merge to Currently Connected Site...',
            ]
        [pending_server_action] = pending_server.context_menu_actions().keys()
        assert pending_server_action in possible_actions

        server_one_credentials = server_vm_one.api.get_credentials()
        server_two_credentials = server_vm_two.api.get_credentials()
        server_two_address, server_two_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm_two)
        MainMenu(testkit_api, hid).activate_merge_systems()
        MergeSystemsDialog(testkit_api, hid).merge_with_configured_server(
            server_one_credentials.password,
            server_two_credentials.username,
            server_two_credentials.password,
            server_two_port,
            server_two_address,
            site_name=server_vm_two_info.site_name,
            )
        resource_tree.wait_for_server_count(expected_count=2)
        assert resource_tree.has_server(server_vm_one.api.get_server_name())
        assert resource_tree.has_server(server_vm_two_info.server_name)


if __name__ == '__main__':
    exit(test_owner_can_merge_sites().main())
