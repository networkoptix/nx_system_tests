# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.testcamera_setup import similar_playing_testcameras
from tests.base_test import VMSTest


class test_resource_tree_state_if_all_resources_are_removed(VMSTest):
    """Resource tree structure state.

    Login as an administrator and add cameras. Switch resource tree to without servers state.
    Remove all cameras. "Cameras & Devices" node remains visible. The resource tree can be switches between states.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84527

    Selection-Tag: 84527
    Selection-Tag: resources_grouping
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        distrib_url = args.distrib_url
        installer_supplier = ClassicInstallerSupplier(distrib_url)
        machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        # same video for multiple cameras
        exit_stack.enter_context(similar_playing_testcameras(machine_pool, server_vm.os_access, 'samples/overlay_test_video.mp4', count=2))
        [test_camera_1, test_camera_2] = server_vm.api.add_test_cameras(0, 2)
        server_vm_name = server_vm.api.get_server_name()
        assert ResourceTree(testkit_api, hid).has_server(server_vm_name)
        ResourceTree(testkit_api, hid).hide_servers()
        assert not ResourceTree(testkit_api, hid).has_server(server_vm_name)
        ResourceTree(testkit_api, hid).get_camera(test_camera_1.name).remove()
        ResourceTree(testkit_api, hid).get_camera(test_camera_2.name).remove()
        assert not ResourceTree(testkit_api, hid).has_server(server_vm_name)
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
        ResourceTree(testkit_api, hid).show_servers()
        assert ResourceTree(testkit_api, hid).has_server(server_vm_name)

        server_node = ResourceTree(testkit_api, hid).get_server(server_vm_name)
        options = server_node.context_menu_actions()
        assert 'Show Servers' in options
        assert options['Show Servers'].checked
        assert 'Monitor' in options
        if installer_supplier.distrib().newer_than('vms_6.0'):
            assert 'Open in' in options
            open_options = server_node.context_submenu_actions('Open in')
            assert 'New Tab' in open_options
            assert 'New Window' in open_options
        else:
            assert 'Monitor in New Tab' in options
            assert 'Monitor in New Window' in options
        assert 'Rename' in options
        assert 'Cameras List by Server...' in options
        assert 'Server Logs...' in options
        assert 'Server Diagnostics...' in options
        assert 'Server Web Page...' in options
        assert 'Server Settings...' in options
        assert 'Add' in options

        add_options = server_node.context_submenu_actions('Add')
        assert 'Proxied Web Page...' in add_options
        assert 'Proxied Integration...' in add_options
        assert 'Virtual Camera...' in add_options
        assert 'Device...' in add_options
        ResourceTree(testkit_api, hid).hide_servers()
        assert not ResourceTree(testkit_api, hid).has_server(server_vm_name)


if __name__ == '__main__':
    exit(test_resource_tree_state_if_all_resources_are_removed().main())
