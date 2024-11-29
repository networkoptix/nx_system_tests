# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.http_server.http_server import create_proxy_image_server
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.edit_webpage import suppress_connect_anyway
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.wrappers import QMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from os_access import current_host_address
from tests.base_test import VMSTest


class test_webpages_proxy_basic_checks(VMSTest):
    """Webpages proxy basic checks.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/116147
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/116157
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/119010

    Selection-Tag: 116147
    Selection-Tag: 116157
    Selection-Tag: 119010
    Selection-Tag: webpages
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [server_vm, client_installation] = exit_stack.enter_context(machine_pool.setup_server_client())
        client_installation.set_ini('desktop_client.ini', {'hideOtherSystemsFromResourceTree': 'true'})
        client_address = '127.0.0.1'
        test_http_server = exit_stack.enter_context(
            create_proxy_image_server(
                ip_addresses_to_check_proxy=[client_address],
                source_address_from_client=client_installation.os_access.source_address(),
                ))
        test_page_url = f'https://{current_host_address()}:{test_http_server.server_port}/'
        testkit_api = start_desktop_client_connected_to_server(
            machine_pool.get_address_and_port_of_server_on_another_machine_for_client(server_vm),
            machine_pool.get_testkit_port(),
            client_installation,
            server_vm,
            )
        hid = HID(testkit_api)
        rtree = ResourceTree(testkit_api, hid)
        assert ['New Web Page...'] == list(rtree.get_webpages_node().context_menu_actions().keys())
        edit_webpage_dialog = rtree.get_webpages_node().open_new_webpage_dialog()
        web_page_item = edit_webpage_dialog.create_resource(
            url=test_page_url,
            name='TestPage',
            )
        suppress_connect_anyway(testkit_api, hid)
        rtree.reload()
        assert rtree.has_webpage('TestPage')
        assert web_page_item.has_phrase('APPLE')
        assert web_page_item.has_phrase('LOCO')
        actual_options = list(web_page_item.open_context_menu().get_options().keys())
        expected_options = [
            'Maximize Item',
            'Show on Item',
            'Remove from Layout',
            'Page...',
            'Web Page Settings...',
            ]
        # Disregard the opening options due to version differences.
        for option in ['Open in New Window', 'Open in New Tab', 'Open in', 'Open in Dedicated Window']:
            if option in actual_options:
                actual_options.remove(option)
        assert sorted(actual_options) == sorted(expected_options)
        QMenu(testkit_api, hid).close()
        dialog = rtree.get_webpage('TestPage').open_settings_dialog()
        dialog.set_proxy_via_server(True)
        dialog.save_and_close()
        suppress_connect_anyway(testkit_api, hid)
        web_page_item.click_button('Refresh')
        assert web_page_item.has_phrase('APPLE')
        assert not web_page_item.has_phrase('LOCO')


if __name__ == '__main__':
    exit(test_webpages_proxy_basic_checks().main())
