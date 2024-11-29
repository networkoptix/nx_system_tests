# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from directories import get_run_dir
from gui.client_start import start_desktop_client
from gui.desktop_ui.dialogs.connect_to_server import first_time_connect
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import CurrentUserNodeNotFound
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.welcome_screen import WelcomeScreen
from gui.desktop_ui.widget import WidgetIsNotAccessible
from gui.gui_test_stand import GuiTestStand
from gui.testkit import TestKit
from gui.testkit import TestKitConnectionError
from gui.testkit.hid import HID
from installation import ClassicInstallerSupplier
from mediaserver_api import LdapSearchBase
from mediaserver_api import MediaserverApi
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import VMSTest


class test_synchronization_with_huge_LDAP(VMSTest):
    """Synchronization with a huge Active Directory database.

    The test runs 3 VMs and lasts for 10 minutes, so it's not advisable to use
    the 'gui-smoke-test' tag.

    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122073

    Selection-Tag: 122073
    Selection-Tag: ldap
    """

    def _run(self, args, exit_stack):
        # Getting groups and users produces very large HTTP responses.
        logging.getLogger('mediaserver_api._mediaserver.http_resp.large').setLevel(logging.INFO)
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        api_version = 'v3plus'
        server_machine_pool = FTMachinePool(installer_supplier, get_run_dir(), api_version)
        ldap_vm_and_mediaserver_vm_network = exit_stack.enter_context(
            server_machine_pool.ldap_vm_and_mediaservers_vm_network(['win11'], 'active_directory'))
        [ldap_server_unit, mediaserver_unit] = ldap_vm_and_mediaserver_vm_network
        ldap_server = ldap_server_unit.installation()
        ldap_address = ldap_server_unit.subnet_ip()
        mediaserver = mediaserver_unit.installation()
        # Synchronization with a large LDAP database consumes a lot of memory and produces a lot of
        # network traffic. Disable traffic capturing and verbose logging for the sake of memory economy.
        mediaserver_unit.os_access().traffic_capture.stop()
        mediaserver.setup_logging_ini(enable_log_file_verbose=False)
        mediaserver.start()
        mediaserver.api.setup_local_system()
        search_base = LdapSearchBase(ldap_server.ou_huge().dn, '', 'users')
        mediaserver.api.set_ldap_settings(
            ldap_address, ldap_server.admin_dn(), ldap_server.password(), [search_base])
        metrics_logger = _LogServerMetrics(mediaserver.api)
        metrics_logger.log_consumed_memory()
        started_at = time.monotonic()
        mediaserver.api.sync_ldap_users(timeout=300)
        _logger.info("LDAP synchronization takes %d seconds", time.monotonic() - started_at)
        metrics_logger.log_consumed_memory()
        groups_count = len([group.name for group in mediaserver.api.list_user_groups() if group.is_ldap])
        ldap_groups_count = ldap_server.ou_huge().count_groups
        assert groups_count >= ldap_groups_count, (
            f"Expected at least {ldap_groups_count} groups, got {groups_count}"
            )
        users = mediaserver.api.list_users()
        ldap_users_count = ldap_server.ou_huge().count_users
        assert len(users) >= ldap_users_count, (
            f"Expected at least {ldap_users_count} users, got {len(users)}"
            )
        ldap_user_name = users[0].name
        del users   # 100k users take a lot of memory. Let's give it to the garbage collector.
        # Check via Desktop Client.
        client_machine_pool = GuiTestStand(installer_supplier, get_run_dir())
        client_installation = exit_stack.enter_context(client_machine_pool.create_and_setup_only_client())
        # Synchronization with a large LDAP catalog produces a huge amount of verbose logs.
        client_installation.create_desktop_client_log_ini(verbose=False)
        testkit_api = start_desktop_client(client_machine_pool.get_testkit_port(), client_installation)
        hid = HID(testkit_api)
        [address, port] = client_machine_pool.get_address_and_port_of_server_on_another_machine_for_client(
            mediaserver_unit.installation())
        started_at = time.monotonic()
        _log_in_to_server(
            testkit_api,
            hid, address,
            port,
            mediaserver.api.get_credentials().username,
            mediaserver.api.get_credentials().password,
            )
        duration = time.monotonic() - started_at
        _logger.info("Connecting as 'admin' took %.1f seconds", duration)
        # Duration values are greater than described in the TestRail case because most GUI
        # operations take some time to execute.
        assert duration <= 70, (
            f"Connecting as 'admin' took {duration:.1f} seconds, but it was expected to take less than 70"
            )
        started_at = time.monotonic()
        _disconnect_from_server(testkit_api, hid)
        duration = time.monotonic() - started_at
        _logger.info("Disconnecting took %.1f seconds", duration)
        assert duration <= 40, (
            f"Disconnecting took {duration:.1f} seconds, but it was expected to take less than 40"
            )
        started_at = time.monotonic()
        _log_in_to_server(testkit_api, hid, address, port, ldap_user_name, ldap_server.password())
        duration = time.monotonic() - started_at
        _logger.info("Connecting as LDAP user '%s' took %.1f seconds", ldap_user_name, duration)
        assert duration <= 20, (
            f"Connecting as an LDAP user took {duration:.1f} seconds, but it was expected to take less than 20"
            )


class _LogServerMetrics:

    def __init__(self, api: MediaserverApi):
        self._api = api
        self._total_ram_usage_mb_prev = None
        self._vms_ram_usage_mb_prev = None

    def log_consumed_memory(self):
        metrics = self._api.get_metrics('servers')
        metrics_load = metrics[self._api.get_server_id()]
        total_ram_usage_mb = metrics_load['total_ram_usage_bytes'] / 1024 / 1024
        vms_ram_usage_mb = metrics_load['vms_ram_usage_bytes'] / 1024 / 1024
        if self._total_ram_usage_mb_prev is None:
            _logger.debug('Total RAM used: %d MB', total_ram_usage_mb)
            _logger.debug('RAM used by VMS: %d MB', vms_ram_usage_mb)
        else:
            _logger.debug(
                'Total RAM used: %d MB, change: %d MB',
                total_ram_usage_mb, total_ram_usage_mb - self._total_ram_usage_mb_prev)
            _logger.debug(
                'RAM used by VMS: %d MB, change: %d MB',
                vms_ram_usage_mb, vms_ram_usage_mb - self._vms_ram_usage_mb_prev)
        self._total_ram_usage_mb_prev = total_ram_usage_mb
        self._vms_ram_usage_mb_prev = vms_ram_usage_mb


def _log_in_to_server(testkit_api: TestKit, hid: HID, address: str, port: int, user, password):
    MainMenu(testkit_api, hid).activate_connect_to_server().connect(address, user, password, port)
    first_time_connect(testkit_api, hid)
    finished_at = time.monotonic() + 90
    while True:
        try:
            ResourceTree(testkit_api, hid).wait_for_current_user(timeout=3)
        except (TestKitConnectionError, CurrentUserNodeNotFound):
            _logger.debug('Desktop Client is not responding.')
        else:
            break
        if time.monotonic() >= finished_at:
            raise RuntimeError('Desktop Client is not responding')
        time.sleep(1)


def _disconnect_from_server(testkit_api: TestKit, hid: HID):
    try:
        MainMenu(testkit_api, hid).disconnect_from_server()
    except TestKitConnectionError:
        _logger.debug("The Desktop Client is hanging for a while, but this is expected")
    welcome_screen = WelcomeScreen(testkit_api, hid)
    finished_at = time.monotonic() + 60
    while True:
        try:
            welcome_screen.wait_for_accessible()
        except WidgetIsNotAccessible:
            _logger.debug('Waiting for disconnect')
        except TestKitConnectionError:
            _logger.debug('Desktop Client is not responding')
        else:
            break
        if time.monotonic() >= finished_at:
            raise RuntimeError('Desktop Client is not responding')
        time.sleep(3)


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(test_synchronization_with_huge_LDAP().main())
