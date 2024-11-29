# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._storage_locations import ModeChoiceEntry
from tests.web_admin._storage_locations import ModeEntryNotFound
from tests.web_admin._storage_locations import StorageLocations
from tests.web_admin._storage_locations import storage_mode_choice_menu
from vm.networks import setup_flat_network


class test_attempt_to_change_single_main(WebAdminTest):
    """Test change storage mode.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84284
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    # The test is simplified. The testcase is created having manual testing in mind,
    # so some users are created for use in subsequent testcases.
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
    [[mediaserver_ip, _], _] = setup_flat_network(
        [mediaserver_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    mediaserver_api = mediaserver_stand.api()
    mediaserver = mediaserver_stand.mediaserver()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    mediaserver.start()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    mediaserver_api.setup_local_system({'licenseServer': license_server.url()})
    local_administrator_credentials = mediaserver_api.get_credentials()
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_servers_link().invoke()
    default_storage_path = mediaserver.default_archive().storage_root_path()
    storages_table = StorageLocations(browser).get_storages_table()
    main_storage_entry = storages_table.find_storage_entry(default_storage_path)
    main_storage_entry.get_mode().invoke()
    choice_menu = storage_mode_choice_menu(browser, installer_supplier.distrib().version())
    backup_entry = choice_menu.get_backup_entry()
    assert not backup_entry.is_enabled(), "Backup entry is enabled initially"
    assert not backup_entry.is_selected(), "Backup entry is selected initially"
    backup_entry.choose()
    assert not backup_entry.is_enabled(), "Backup entry is enabled after choose"
    assert not backup_entry.is_selected(), "Backup entry is selected after choose"
    not_in_use_entry = choice_menu.get_not_in_use_entry()
    assert not not_in_use_entry.is_enabled(), "Not In Use entry is enabled initially"
    assert not not_in_use_entry.is_selected(), "Not In Use entry is selected initially"
    not_in_use_entry.choose()
    assert not not_in_use_entry.is_enabled(), "Not In Use entry is enabled after choose"
    assert not not_in_use_entry.is_selected(), "Not In Use entry is selected after choose"
    main_entry = choice_menu.get_main_entry()
    assert main_entry.is_enabled(), "Main entry is not enabled initially"
    assert main_entry.is_selected(), "Main entry is not selected initially"
    main_entry.choose()
    assert not _is_present(main_entry)
    assert not _is_present(backup_entry)
    assert not _is_present(not_in_use_entry)


def _is_present(entry: ModeChoiceEntry) -> bool:
    try:
        entry.choose()
    except ModeEntryNotFound:
        return False
    return True


_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_attempt_to_change_single_main()]))
