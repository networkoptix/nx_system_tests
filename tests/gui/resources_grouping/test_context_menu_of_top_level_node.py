# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from distrib import BranchNotSupported
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.server_login_steps import _log_in_using_main_menu
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_context_menu_of_top_level_node(VMSTest):
    """Context menu of top level node.

    Check of top level node for owner, administrator and viewer.

    #  https://networkoptix.testrail.net/index.php?/cases/view/84528

    Selection-Tag: 84528
    Selection-Tag: resources_grouping
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        if installer_supplier.distrib().newer_than('vms_6.0'):
            raise BranchNotSupported("Test should be fixed for VMS 6.1+")

        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        server_vm.api.add_local_admin('Administrator', 'WellKnownPassword2')
        server_vm.api.add_local_viewer('Viewer', 'WellKnownPassword2')
        # same video for multiple cameras
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4', count=2))
        server_vm.api.add_test_cameras(0, 2)

        server_node = ResourceTree(testkit_api, hid).get_server(server_vm.api.get_server_name())
        options1 = server_node.context_menu_actions()
        assert 'Show Servers' in options1
        assert 'Show Proxied Resources' in options1
        assert options1['Show Servers'].checked
        assert 'Monitor' in options1
        if installer_supplier.distrib().newer_than('vms_6.0'):
            assert 'Open in' in options1
            open_options = server_node.context_submenu_actions('Open in')
            assert 'New Tab' in open_options
            assert 'New Window' in open_options
        else:
            assert 'Monitor in New Tab' in options1
            assert 'Monitor in New Window' in options1
        assert 'Rename' in options1
        assert 'Cameras List by Server...' in options1
        assert 'Server Logs...' in options1
        assert 'Server Diagnostics...' in options1
        assert 'Server Web Page...' in options1
        assert 'Server Settings...' in options1
        assert 'Add' in options1

        add_options = server_node.context_submenu_actions('Add')
        assert 'Device...' in add_options
        assert 'Proxied Integration...' in add_options
        assert 'Proxied Web Page...' in add_options
        assert 'Virtual Camera...' in add_options

        ResourceTree(testkit_api, hid).hide_servers()
        cur_options = ResourceTree(testkit_api, hid).get_all_resources_node().context_menu_actions()
        assert 'Show Servers' in cur_options
        assert not cur_options['Show Servers'].checked
        assert 'Open Web Client...' in cur_options
        # The word "System" is used in VMS 6.0. The word "Site" is used for newer versions.
        if installer_supplier.distrib().newer_than('vms_6.0'):
            assert 'Merge Sites...' in cur_options
            assert 'Site Administration...' in cur_options
        else:
            assert 'Merge Systems...' in cur_options
            assert 'System Administration...' in cur_options
        main_menu = MainMenu(testkit_api, hid)
        main_menu.disconnect_from_server()

        address_port = machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm)
        _log_in_using_main_menu(testkit_api, hid, address_port, 'Administrator', 'WellKnownPassword2')
        ResourceTree(testkit_api, hid).hide_servers()
        options2 = ResourceTree(testkit_api, hid).get_all_resources_node().context_menu_actions()
        assert 'Show Servers' in options2
        assert not options2['Show Servers'].checked
        assert 'Open Web Client...' in options2
        if installer_supplier.distrib().newer_than('vms_6.0'):
            assert 'Site Administration...' in options2
        else:
            assert 'System Administration...' in options2
        system_administration_dialog_1 = main_menu.activate_system_administration()
        system_administration_dialog_1.open_tab('Security')
        system_administration_dialog_1.security_tab.set_display_servers_for_non_administrators(True)
        system_administration_dialog_1.save_and_close()
        ResourceTree(testkit_api, hid).show_servers()
        main_menu.disconnect_from_server()

        _log_in_using_main_menu(testkit_api, hid, address_port, 'Viewer', 'WellKnownPassword2')
        ResourceTree(testkit_api, hid).hide_servers()
        options3 = ResourceTree(testkit_api, hid).get_all_resources_node().context_menu_actions()
        assert 'Show Servers' in options3
        assert not options3['Show Servers'].checked
        assert 'Open Web Client...' in options3
        ResourceTree(testkit_api, hid).show_servers()
        options4 = ResourceTree(testkit_api, hid).get_server(server_vm.api.get_server_name()).context_menu_actions()
        assert 'Show Servers' in options4
        assert options4['Show Servers'].checked
        assert 'Monitor' in options4
        if installer_supplier.distrib().newer_than('vms_6.0'):
            assert 'Open in' in options4
            open_options = server_node.context_submenu_actions('Open in')
            assert 'New Tab' in open_options
            assert 'New Window' in open_options
        else:
            assert 'Monitor in New Tab' in options4
            assert 'Monitor in New Window' in options4
        main_menu.disconnect_from_server()

        _log_in_using_main_menu(testkit_api, hid, address_port, 'Administrator', 'WellKnownPassword2')
        system_administration_dialog_2 = main_menu.activate_system_administration()
        system_administration_dialog_2.open_tab('Security')
        system_administration_dialog_2.security_tab.set_display_servers_for_non_administrators(False)
        system_administration_dialog_2.save_and_close()
        main_menu.disconnect_from_server()

        _log_in_using_main_menu(testkit_api, hid, address_port, 'Viewer', 'WellKnownPassword2')
        options5 = ResourceTree(testkit_api, hid).get_all_resources_node().context_menu_actions()
        assert 'Open Web Client...' in options5


if __name__ == '__main__':
    exit(test_context_menu_of_top_level_node().main())
