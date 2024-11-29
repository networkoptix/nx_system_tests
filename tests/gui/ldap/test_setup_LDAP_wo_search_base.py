# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client_connected_to_server
from gui.desktop_ui.dialogs.ldap_advanced_settings import SynchronizeUsersState
from gui.desktop_ui.dialogs.system_administration import SystemAdministrationDialog
from gui.desktop_ui.dialogs.user_management import LDAPConnectionStatus
from gui.desktop_ui.dialogs.user_management import SynchronisationIssue
from gui.desktop_ui.main_menu import MainMenu
from gui.gui_test_stand import GuiTestStand
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from tests.base_test import VMSTest
from tests.infra import assert_raises


class test_setup_LDAP_wo_search_base(VMSTest):
    """Set up LDAP server without search base.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/119093

    Selection-Tag: 119093
    Selection-Tag: ldap
    Selection-Tag: gui-smoke-test
    """

    def _run(self, args, exit_stack):
        machine_pool = GuiTestStand(ClassicInstallerSupplier(args.distrib_url), get_run_dir())
        [client_stand, mediaserver_unit, ldap_unit] = exit_stack.enter_context(
            machine_pool.setup_server_client_ldap())
        ldap_server = ldap_unit.installation()
        testkit_api = start_desktop_client_connected_to_server(
            server_address_port=(mediaserver_unit.subnet_ip(), 7001),
            testkit_port=client_stand.get_testkit_port(),
            client_installation=client_stand.installation(),
            server=mediaserver_unit.installation(),
            )
        hid = HID(testkit_api)
        main_menu = MainMenu(testkit_api, hid)
        user_management = main_menu.activate_user_management()
        groups_before_synchronization = set(user_management.get_groups_names())
        _logger.info("Configure LDAP")
        ldap_tab = user_management.get_ldap_tab()
        ldap_connection_dialog = ldap_tab.open_configure_dialog()
        ldap_connection_dialog.fill_parameters(
            ldap_unit.subnet_ip(), ldap_server.admin_dn(), ldap_server.password())
        ldap_connection_dialog.click_ok()
        search_base_not_found = re.compile('Specify.*search base.*')
        assert ldap_tab.has_message(search_base_not_found), (
            "Expected message 'Specify at least one search base to synchronize users and groups' "
            "but it was not found")
        _logger.info("Check advanced settings")
        advanced_settings = ldap_tab.open_advanced_settings()
        synchronize_users_state = advanced_settings.get_synchronize_users_state()
        assert synchronize_users_state == SynchronizeUsersState.ALWAYS, (
            f"The 'Synchronize Users' field is expected to have the value "
            f"{SynchronizeUsersState.ALWAYS.value!r} by default, but it is set to "
            f"{synchronize_users_state.value!r}")
        advanced_settings.click_ok()
        synchronization_started_at = time.monotonic()
        SystemAdministrationDialog(testkit_api, hid).save_and_close()
        _logger.info("Check the connection settings")
        user_management = main_menu.activate_user_management()
        ldap_tab = user_management.get_ldap_tab()
        _wait_ldap_server_become_online(ldap_tab, timeout=10)
        assert ldap_tab.is_address_displayed(ldap_unit.subnet_ip()), (
            f"Expected the LDAP address {ldap_unit.subnet_ip()} is not displayed")
        assert_msg = "Users and groups should not be synchronized since the search base has not been set"
        with assert_raises(SynchronisationIssue, assert_msg):
            ldap_tab.get_users_and_groups_count()
        ldap_tab.get_last_sync_time_min()
        assert ldap_tab.has_message(search_base_not_found), (
            "Expected message 'Specify at least one search base to synchronize users and groups', "
            "but it was not found")
        message_banners = ldap_tab.list_message_banners()
        part_of_expected_msg = 'No users or groups match synchronization settings'
        assert len(message_banners) == 1 and part_of_expected_msg in message_banners[0], (
            f"Expected only one message banner and it should be start with {part_of_expected_msg!r}. "
            f"Currently displayed message banners: {message_banners}")
        _logger.info("Check the synchronization results")
        started_at_last_sync_time = ldap_tab.get_last_sync_time_min()
        finished_at = time.monotonic() + 60
        while True:
            last_sync_time = ldap_tab.get_last_sync_time_min()
            if last_sync_time != started_at_last_sync_time:
                break
            if time.monotonic() > finished_at:
                raise RuntimeError(
                    "Last synchronization time has not changed after 60 seconds. The current "
                    f"value is {last_sync_time}")
            time.sleep(5)
        expected_time_min = int((time.monotonic() - synchronization_started_at) / 60)
        assert last_sync_time == expected_time_min, (
            f"Expected {expected_time_min} minutes since the last synchronization, "
            f"but spend {last_sync_time}")
        groups = set(user_management.get_groups_names()) - groups_before_synchronization
        expected_group = 'LDAP Default'
        assert len(groups) == 1 and list(groups)[0] == expected_group, (
            f"Expected one appended group: {expected_group!r}, but received {groups}")
        users = user_management.get_users_names()
        assert len(users) == 1, f"Expected no imported users. Current users list: {users}"


def _wait_ldap_server_become_online(ldap_tab, timeout: float):
    finished_at = time.monotonic() + timeout
    while True:
        ldap_connection_status = ldap_tab.get_connection_status()
        if ldap_connection_status == LDAPConnectionStatus.ONLINE:
            break
        if time.monotonic() > finished_at:
            raise RuntimeError(
                f"The connection status has not became {LDAPConnectionStatus.ONLINE.value!r} "
                f"after 10 seconds. The current status is {ldap_connection_status.value!r}")
        time.sleep(1)


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(test_setup_LDAP_wo_search_base().main())
