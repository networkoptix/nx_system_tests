# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.timeline import TimelinePlaceholder
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_scenarios.prerequisite_upload import gui_prerequisite_supplier
from tests.base_test import VMSTest


class test_upload_video_files_without_timestamp(VMSTest):
    """Impossible to upload video files without timestamp.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/41529

    Selection-Tag: 41529
    Selection-Tag: virtual_cameras
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        server_vm.api.add_virtual_camera('VirtualCamera')
        ResourceTree(testkit_api, hid).wait_for_camera_on_server(server_vm.api.get_server_name(), 'VirtualCamera')
        camera_node = ResourceTree(testkit_api, hid).get_camera('VirtualCamera')
        upload_dialog = camera_node.open_upload_file_dialog()
        file_on_client = gui_prerequisite_supplier.upload_to_remote('upload/no_timestamp.mp4', client_installation.os_access)
        upload_dialog.multi_upload_files([file_on_client], 0)
        message_dialog = MessageBox(testkit_api, hid)
        assert message_dialog.wait_until_appears(20).get_title() == 'Selected file does not have timestamp'
        message_dialog.close_by_button('OK')
        camera_node.open_in_new_tab().wait_for_accessible()
        assert TimelinePlaceholder(testkit_api).is_enabled()


if __name__ == '__main__':
    exit(test_upload_video_files_without_timestamp().main())
