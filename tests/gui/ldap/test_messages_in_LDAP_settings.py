# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest


class test_messages_in_LDAP_settings(VMSTest):
    """Connection to LDAP.

    Selection-Tag: ldap
    Selection-Tag: gui-smoke-test
    Selection-Tag: 120480
    Selection-Tag: 115075
    Selection-Tag: 115074
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/120480
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/115075
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/115074
    """

    def _run(self, args, exit_stack):
        # Background.
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [client_stand, mediaserver_unit, ldap_unit] = exit_stack.enter_context(
            machine_pool.setup_server_client_ldap())
        ldap_server = ldap_unit.installation()
        testkit_api = start_desktop_client_connected_to_server(
            server_address_port=(mediaserver_unit.subnet_ip(), mediaserver_unit.installation().port),
            testkit_port=client_stand.get_testkit_port(),
            client_installation=client_stand.installation(),
            server=mediaserver_unit.installation(),
            )
        hid = HID(testkit_api)
        # VMSTest.
        main_menu = MainMenu(testkit_api, hid)
        dialog = main_menu.activate_user_management()
        ldap_connection_dialog = dialog.get_ldap_tab().open_configure_dialog()
        ldap_connection_dialog.fill_parameters(
            'incorrect host', ldap_server.admin_dn(), ldap_server.password())
        ldap_connection_dialog.click_test_button()
        error_message_text = ldap_connection_dialog.get_error_message_text()
        expected_error_text = 'Cannot connect to LDAP server.'
        assert error_message_text == expected_error_text, (
            f'Expected: {expected_error_text!r}. Actual: {error_message_text!r}')
        ldap_connection_dialog.fill_parameters(
            ldap_unit.subnet_ip(), ldap_server.admin_dn(), 'incorrect password')
        ldap_connection_dialog.click_test_button()
        error_message_text = ldap_connection_dialog.get_error_message_text()
        expected_error_text = 'Invalid LDAP credentials.'
        assert error_message_text == expected_error_text, (
            f'Expected: {expected_error_text!r}. Actual: {error_message_text!r}')
        ldap_connection_dialog.fill_parameters('', ldap_server.admin_dn(), 'incorrect password')
        warning_messages = ldap_connection_dialog.get_warning_messages()
        expected_messages = ['Host cannot be empty']
        assert warning_messages == expected_messages, (
            f'Expected: {expected_messages}. Actual: {warning_messages}')
        ldap_connection_dialog.fill_parameters(ldap_unit.subnet_ip(), '', 'incorrect password')
        ldap_connection_dialog.click_ok()
        warning_messages = ldap_connection_dialog.get_warning_messages()
        expected_messages = ['Login DN cannot be empty']
        assert warning_messages == expected_messages, (
            f'Expected: {expected_messages}. Actual: {warning_messages}')
        ldap_connection_dialog.fill_parameters(ldap_unit.subnet_ip(), ldap_server.admin_dn(), '')
        ldap_connection_dialog.click_ok()
        warning_messages = ldap_connection_dialog.get_warning_messages()
        expected_messages = ['Password cannot be empty']
        assert warning_messages == expected_messages, (
            f'Expected: {expected_messages}. Actual: {warning_messages}')
        ldap_connection_dialog.fill_parameters(ldap_unit.subnet_ip(), '', '')
        ldap_connection_dialog.click_ok()
        warning_messages = ldap_connection_dialog.get_warning_messages()
        expected_messages = ['Login DN cannot be empty', 'Password cannot be empty']
        assert warning_messages == expected_messages, (
            f'Expected: {expected_messages}. Actual: {warning_messages}')


if __name__ == '__main__':
    exit(test_messages_in_LDAP_settings().main())
