# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.system_administration import SystemAdministrationDialog
from gui.desktop_ui.dialogs.user_management import SynchronisationIssue
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from os_access.ldap.server_installation import GeneratedLDAPUser
from tests.base_test import VMSTest
from tests.infra import assert_raises


class test_setup_LDAP_server(VMSTest):
    """Set up LDAP server with search base.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/115077

    Selection-Tag: 115077
    Selection-Tag: ldap
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [client_stand, mediaserver_unit, ldap_unit] = exit_stack.enter_context(
            machine_pool.setup_server_client_ldap())
        ldap_server = ldap_unit.installation()
        ldap_users = set()
        ldap_groups = set()
        for index in range(1, 4):
            generated_ldap_user = GeneratedLDAPUser('Test', f'User_{index}')
            ldap_server.add_users([generated_ldap_user.attrs()])
            ldap_users.add(generated_ldap_user.uid)
            ldap_server.add_group(f'ldap_group_{index}')
            ldap_groups.add(f'ldap_group_{index}')
        testkit_api = start_desktop_client_connected_to_server(
            server_address_port=(mediaserver_unit.subnet_ip(), 7001),
            testkit_port=client_stand.get_testkit_port(),
            client_installation=client_stand.installation(),
            server=mediaserver_unit.installation(),
            )
        hid = HID(testkit_api)
        main_menu = MainMenu(testkit_api, hid)
        _logger.debug("Test LDAP connection")
        user_management = main_menu.activate_user_management()
        ldap_tab = user_management.get_ldap_tab()
        ldap_connection_dialog = ldap_tab.open_configure_dialog()
        ldap_connection_dialog.fill_parameters(
            ldap_unit.subnet_ip(), ldap_server.admin_dn(), ldap_server.password())
        ldap_connection_dialog.click_test_button()
        message_text = ldap_connection_dialog.get_error_message_text()
        assert message_text == 'Connection OK', f"Expected 'Connection OK' message, got {message_text}"
        ldap_connection_dialog.click_ok()
        SystemAdministrationDialog(testkit_api, hid).cancel_and_close()
        _logger.debug("Test without entering the search base")
        user_management = main_menu.activate_user_management()
        ldap_tab = user_management.get_ldap_tab()
        ldap_connection_dialog = ldap_tab.open_configure_dialog()
        ldap_connection_dialog.fill_parameters(
            ldap_unit.subnet_ip(), ldap_server.admin_dn(), ldap_server.password())
        ldap_connection_dialog.click_ok()
        assert ldap_tab.has_message(re.compile('Specify.*search base.*')), (
            "Expected message 'Specify at least one search base to synchronize users and groups' "
            "but it was not found")
        SystemAdministrationDialog(testkit_api, hid).save_and_close()
        _logger.debug("Test with a fully configured LDAP connection")
        user_management = main_menu.activate_user_management()
        ldap_tab = user_management.get_ldap_tab()
        assert_msg = "Users and groups should not be synchronized since the search base has not been set"
        with assert_raises(SynchronisationIssue, assert_msg):
            ldap_tab.get_users_and_groups_count()
        ldap_tab.add_search_base('Search base for users', ldap_server.users_ou(), '')
        ldap_tab.add_search_base('Search base for groups', ldap_server.groups_ou(), '')
        SystemAdministrationDialog(testkit_api, hid).apply_changes()
        ldap_tab.wait_until_synchronization_completed()
        [_, count_groups] = ldap_tab.get_users_and_groups_count()
        assert count_groups == len(ldap_groups), (
            f"Expected the group counter to be {len(ldap_groups)}, but got {count_groups}")
        SystemAdministrationDialog(testkit_api, hid).save_and_close()
        _logger.debug("Check users and groups")
        user_management = main_menu.activate_user_management()
        users = set(user_management.get_users_names())
        assert ldap_users <= users, (
            f"Expected that all LDAP users ({ldap_users!r} to be imported, but the current list "
            f"of users is: {users!r}")
        groups = set(user_management.get_groups_names())
        assert ldap_groups <= groups, (
            f"Expected that all LDAP groups ({ldap_groups!r} to be imported, but the current list "
            f"of groups is: {groups!r}")


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(test_setup_LDAP_server().main())
