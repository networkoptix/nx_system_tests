# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_api import LdapSearchBase
from os_access.ldap.server_installation import GeneratedLDAPUser
from tests.base_test import VMSTest


class test_assign_users_to_groups_LDAP(VMSTest):
    """Check assigning LDAP users and groups.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/119229
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/119240
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/120459

    Selection-Tag: 119229
    Selection-Tag: 119240
    Selection-Tag: 120459
    Selection-Tag: ldap
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        _logger.info("Prepare the stand")
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [client_stand, mediaserver_unit, ldap_unit] = exit_stack.enter_context(
            machine_pool.setup_server_client_ldap())
        ldap_server = ldap_unit.installation()
        mediaserver = mediaserver_unit.installation()
        search_base = [
            LdapSearchBase(ldap_server.users_ou(), '', 'users'),
            LdapSearchBase(ldap_server.groups_ou(), '', 'groups'),
            ]
        mediaserver.api.set_ldap_settings(
            ldap_unit.subnet_ip(), ldap_server.admin_dn(), ldap_server.password(), search_base)
        ldap_user = GeneratedLDAPUser('Test', 'User')
        ldap_server.add_users([ldap_user.attrs()])
        ldap_empty_group_name = 'test_empty_group'
        ldap_server.add_group(ldap_empty_group_name)
        ldap_subgroup_name = 'test_subgroup'
        ldap_server.add_group(ldap_subgroup_name)
        ldap_group_name = 'test_group'
        ldap_server.add_group(ldap_group_name, members=[ldap_user.uid], subgroups=[ldap_subgroup_name])
        mediaserver.api.sync_ldap_users()
        testkit_api = start_desktop_client_connected_to_server(
            server_address_port=(mediaserver_unit.subnet_ip(), mediaserver.port),
            testkit_port=client_stand.get_testkit_port(),
            client_installation=client_stand.installation(),
            server=mediaserver,
            )
        hid = HID(testkit_api)
        main_menu = MainMenu(testkit_api, hid)
        user_management = main_menu.activate_user_management()
        _logger.info("Check the assigned groups")
        user_settings = user_management.open_user_settings(ldap_user.uid)
        general_tab = user_settings.select_general_tab()
        selected_group_names = general_tab.get_selected_groups_names()
        assert 'LDAP Default' in selected_group_names, (
            f"It is expected that the user {ldap_user.uid} is assigned to the 'LDAP Default' group")
        groups_tab = user_settings.select_groups_tab()
        group_names = set(groups_tab.list_groups(selected=True))
        expected_group_names = {'LDAP Default', ldap_group_name}
        assert expected_group_names == group_names, (
            f"Expected that {expected_group_names} are assigned, but got only {group_names}")
        group_names = set(groups_tab.get_existing_group_names())
        assert expected_group_names == group_names, (
            f"Expected that {expected_group_names} are assigned, but got {group_names}")
        _logger.info("Try to unassign LDAP groups")
        groups_tab.toggle_group('LDAP Default')
        groups_tab.toggle_group(ldap_group_name)
        group_names = set(groups_tab.list_groups(selected=True))
        expected_group_names = {'LDAP Default', ldap_group_name}
        assert expected_group_names == group_names, (
            f"Expected that {expected_group_names} are assigned, but got {group_names}")
        user_settings.save_and_close()
        _logger.info("Try to add and remove a LDAP group to/from another LDAP group")
        group_settings = user_management.open_group_settings(ldap_subgroup_name)
        if not mediaserver.older_than('vms_6.1'):
            # In versions above 6.1, elements with assigned groups may be recreated at arbitrary
            # moments after the tab is opened. This causes instability in the test logic.
            # So, make this check only for 6.1+.
            general_tab = group_settings.get_general_tab()
            general_tab.is_possible_to_exclude_group(ldap_group_name)
        groups_tab = group_settings.get_groups_tab()
        groups_tab.unselect_group(ldap_group_name)
        selected_group_names = groups_tab.list_groups(selected=True)
        assert [ldap_group_name] == selected_group_names, (
            f"It is expected that LDAP group {ldap_subgroup_name!r} cannot be removed from "
            f"{ldap_group_name!r}")
        unselected_group_names = groups_tab.list_groups(selected=False)
        assert ldap_empty_group_name not in unselected_group_names, (
            f"The group {ldap_empty_group_name!r} is expected to be inaccessible for assignment")
        _logger.info("Try to remove LDAP user from LDAP group")
        group_settings.click_cancel_button()
        group_settings = user_management.open_group_settings(ldap_group_name)
        members_tab = group_settings.get_members_tab()
        selectable_members = members_tab.get_selectable_group_members()
        assert ldap_user.uid not in selectable_members, (
            f"Is it expected that removing LDAP user {ldap_user.uid!r} from the LDAP group "
            f"{ldap_group_name!r} is not allowed")
        group_settings.click_cancel_button()
        group_settings = user_management.open_group_settings('LDAP Default')
        members_tab = group_settings.get_members_tab()
        selectable_members = members_tab.get_selectable_group_members()
        assert ldap_user.uid not in selectable_members, (
            f"Is it expected that removing LDAP user {ldap_user.uid!r} from the 'LDAP Default' "
            "group is not allowed")


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(test_assign_users_to_groups_LDAP().main())
