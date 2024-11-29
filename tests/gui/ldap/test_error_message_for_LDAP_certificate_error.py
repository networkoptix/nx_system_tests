# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.user_management import LDAPConnectionStatus
from gui.desktop_ui.dialogs.user_management import SynchronisationIsNotPerformed
from gui.desktop_ui.dialogs.user_management import SynchronisationIssue
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest
from tests.infra import assert_raises


class test_error_message_for_LDAP_certificate_error(VMSTest):
    """Connection to LDAP.

    Selection-Tag: ldap
    Selection-Tag: 120481
    Selection-Tag: gui-smoke-test
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/120481
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [client_stand, mediaserver_unit, ldap_unit] = exit_stack.enter_context(
            machine_pool.setup_server_client_ldap())
        ldap_server = ldap_unit.installation()
        ldap_server.configure_tls('localhost')
        testkit_api = start_desktop_client_connected_to_server(
            server_address_port=(mediaserver_unit.subnet_ip(), 7001),
            testkit_port=client_stand.get_testkit_port(),
            client_installation=client_stand.installation(),
            server=mediaserver_unit.installation(),
            )
        hid = HID(testkit_api)
        main_menu = MainMenu(testkit_api, hid)
        user_management = main_menu.activate_user_management()
        _logger.info("Configure LDAP")
        ldap_tab = user_management.get_ldap_tab()
        ldap_connection_dialog = ldap_tab.open_configure_dialog()
        ldap_connection_dialog.set_ldap_scheme('ldaps://')
        ldap_connection_dialog.fill_parameters(
            ldap_unit.subnet_ip(), ldap_server.admin_dn(), ldap_server.password())
        ldap_connection_dialog.click_test_button()
        error_message_text = ldap_connection_dialog.get_error_message_text()
        expected_error_text = 'Connection failed due to certificate error.'
        assert error_message_text == expected_error_text, (
            f'Expected: {expected_error_text}. Actual: {error_message_text}')
        ldap_connection_dialog.click_ok()
        _logger.info("Check connection status")
        ldap_connection_status = ldap_tab.get_connection_status()
        assert ldap_connection_status == LDAPConnectionStatus.OFFLINE, (
            f"The connection status should be {LDAPConnectionStatus.ONLINE.value!r}, got "
            f"{ldap_connection_status.value!r}")
        assert_msg = "Users and groups should not be synchronized"
        with assert_raises(SynchronisationIssue, assert_msg):
            ldap_tab.get_users_and_groups_count()
        assert_msg = "The last time synchronization should not be set"
        with assert_raises(SynchronisationIsNotPerformed, assert_msg):
            ldap_tab.get_last_sync_time_min()


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(test_error_message_for_LDAP_certificate_error().main())
