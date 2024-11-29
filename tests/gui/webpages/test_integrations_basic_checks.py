# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from doubles.http_server.http_server import create_proxy_image_server
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.edit_webpage import EditIntegration
from gui.desktop_ui.dialogs.edit_webpage import suppress_connect_anyway
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import IntegrationSceneItem
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from os_access import current_host_address
from tests.base_test import VMSTest


class test_integrations_basic_checks(VMSTest):
    """Integrations basic checks.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/119011
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/116743
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/116178

    Selection-Tag: 119011
    Selection-Tag: 116743
    Selection-Tag: 116178
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
        dialog = MainMenu(testkit_api, hid).activate_new_integration()
        expected_warning = (
            "An integration may interact with the Desktop Client "
            "and request access to the user session")
        assert dialog.get_warning_text() == expected_warning
        assert not dialog.get_proxy_via_server_checkbox().is_checked()
        dialog.switch_tab('Advanced')
        assert not dialog.proxy_all_content_is_enabled()
        assert not dialog.get_disable_sll_checkbox().is_checked()
        assert dialog.get_warning_text() == expected_warning
        dialog.create_resource(
            url=test_page_url,
            name='TestIntegration',
            )
        suppress_connect_anyway(testkit_api, hid)
        rtree = ResourceTree(testkit_api, hid)
        rtree.wait_for_integration_node('TestIntegration')
        integration_item = IntegrationSceneItem(testkit_api, hid, 'TestIntegration')
        integration_item.wait_for_accessible()
        integration_item.wait_for_phrase_exists('APPLE')  # A web page may appear with a delay.
        assert integration_item.has_phrase('LOCO')
        menu = integration_item.open_context_menu()
        actual_options = list(menu.get_options().keys())
        expected_options = [
            'Maximize Item',
            'Show on Item',
            'Remove from Layout',
            'Page...',
            'Integration Settings...',
            ]
        if server_vm.api.server_newer_than('vms_6.0'):
            expected_options.append('JavaScript API...')
        # Disregard the opening options due to version differences.
        for option in ['Open in New Window', 'Open in New Tab', 'Open in', 'Open in Dedicated Window']:
            if option in actual_options:
                actual_options.remove(option)
        assert sorted(actual_options) == sorted(expected_options)
        menu.activate_items('Integration Settings...')
        dialog = EditIntegration(testkit_api, hid)
        dialog.set_proxy_via_server(True)
        dialog.save_and_close()
        suppress_connect_anyway(testkit_api, hid)
        integration_item.click_button('Refresh')
        integration_item.wait_for_phrase_exists('APPLE')  # A web page may appear with a delay.
        assert not integration_item.has_phrase('LOCO')
        integration_item.click_button('Fullscreen')
        integration_item.wait_for_expanded()
        # Exit fullscreen mode by pressing Escape button.
        hid.keyboard_hotkeys('Escape')
        assert integration_item.get_information() == test_page_url
        integration_item.click_button('Close')
        integration_item.wait_for_inaccessible()
        integration_node = rtree.wait_for_proxied_integration_node('TestIntegration')
        integration_node.rename_using_context_menu('Renamed integration')
        rtree.reload()
        assert not rtree.has_proxied_integration('TestIntegration')
        integration_node = rtree.wait_for_proxied_integration_node('Renamed integration')
        integration_node.start_removing()
        MessageBox(testkit_api, hid).click_button_with_text('Delete')
        rtree.reload()
        assert not rtree.has_proxied_integration('Renamed integration')
        assert not rtree.has_integrations_node()


if __name__ == '__main__':
    exit(test_integrations_basic_checks().main())
