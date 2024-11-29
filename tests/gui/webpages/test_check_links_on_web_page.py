# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.http_server.http_server import create_test_http_server
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree import ResourceTree
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from os_access import current_host_address
from tests.base_test import VMSTest


class test_check_links_on_web_page(VMSTest):
    """Check links on web page.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/4607

    Selection-Tag: 4607
    Selection-Tag: camera_management
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        test_http_server = exit_stack.enter_context(
            create_test_http_server('page_with_link'))
        server_vm.api.add_web_page('new_web_page', f'http://{current_host_address()}:{test_http_server.server_port}')
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        scene_item = ResourceTree(testkit_api, hid).get_webpage('new_web_page').open()
        scene_item.wait_for_phrase_exists('CLICK')
        center = scene_item.get_phrase_center('CLICK')
        hid.mouse_left_click(center)
        msg_box = MessageBox(testkit_api, hid)
        if msg_box.is_accessible():
            msg_box.close_by_button('Cancel')
        scene_item.wait_for_phrase_exists('ORANGE')


if __name__ == '__main__':
    exit(test_check_links_on_web_page().main())
