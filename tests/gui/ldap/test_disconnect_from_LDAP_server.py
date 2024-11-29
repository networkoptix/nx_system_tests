# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.system_administration import SystemAdministrationDialog
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from os_access.ldap.server_installation import GeneratedLDAPUser
from tests.base_test import VMSTest


class test_disconnect_from_LDAP_server(VMSTest):
    """Disconnect VMS from LDAP server.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/119227

    Selection-Tag: 119227
    Selection-Tag: ldap
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        _logger.info("Prepare the stand")
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
            server_address_port=(mediaserver_unit.subnet_ip(), mediaserver_unit.installation().port),
            testkit_port=client_stand.get_testkit_port(),
            client_installation=client_stand.installation(),
            server=mediaserver_unit.installation(),
            )
        hid = HID(testkit_api)
        main_menu = MainMenu(testkit_api, hid)
        _logger.info("Configure the LDAP connection")
        user_management = main_menu.activate_user_management()
        ldap_tab = user_management.get_ldap_tab()
        ldap_connection_dialog = ldap_tab.open_configure_dialog()
        ldap_connection_dialog.fill_parameters(
            ldap_unit.subnet_ip(), ldap_server.admin_dn(), ldap_server.password())
        ldap_connection_dialog.click_ok()
        ldap_tab.add_search_base('Search base for users', ldap_server.users_ou(), '')
        ldap_tab.add_search_base('Search base for groups', ldap_server.groups_ou(), '')
        SystemAdministrationDialog(testkit_api, hid).apply_changes()
        ldap_tab.wait_until_synchronization_completed()
        _logger.info("Open the Disconnect message box and close it without disconnecting")
        ldap_tab.open_disconnect_message_box().close_by_button('Cancel')
        user_management = main_menu.activate_user_management()
        users = set(user_management.get_users_names())
        assert ldap_users <= users, (
            f"Expected that all LDAP users ({ldap_users}) should remain, but the current list "
            f"of users is: {users}")
        groups = set(user_management.get_groups_names())
        assert ldap_groups <= groups, (
            f"Expected that all LDAP groups ({ldap_groups}) should remain, but the current list "
            f"of groups is: {groups}")
        _logger.info("Open the Disconnect message box and disconnect")
        ldap_tab = user_management.get_ldap_tab()
        ldap_tab.open_disconnect_message_box().close_by_button('Disconnect')
        assert ldap_tab.get_configure_button().is_accessible(), (
            "The 'Configure' button is expected to be accessible.")
        user_management = main_menu.activate_user_management()
        users = set(user_management.get_users_names())
        assert not users.intersection(ldap_users), (
            f"Expected that all LDAP users ({ldap_users}) should disappear, but the current list "
            f"of users is: {users}")
        groups = set(user_management.get_groups_names())
        assert not groups.intersection(ldap_groups), (
            f"Expected that all LDAP groups ({ldap_groups}) should disappear, but the current list "
            f"of groups is: {groups}")


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(test_disconnect_from_LDAP_server().main())
