# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_delete_camera(VMSTest):
    """Delete virtual camera.

    Remove virtual camera by context menu

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/42993

    Selection-Tag: 42993
    Selection-Tag: virtual_cameras
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        server_vm.api.add_virtual_camera('VirtualCamera')
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        ResourceTree(testkit_api, hid).get_camera('VirtualCamera').start_removing()
        message_dialog = MessageBox(testkit_api, hid)
        assert message_dialog.wait_until_appears(20).get_title() == 'Delete 1 camera?'
        message_dialog.close_by_button('Cancel')
        rtree = ResourceTree(testkit_api, hid)
        assert rtree.has_camera('VirtualCamera')

        rtree.get_camera('VirtualCamera').start_removing()
        MessageBox(testkit_api, hid).close_by_button('Delete')
        assert not ResourceTree(testkit_api, hid).has_camera('VirtualCamera')


if __name__ == '__main__':
    exit(test_delete_camera().main())
