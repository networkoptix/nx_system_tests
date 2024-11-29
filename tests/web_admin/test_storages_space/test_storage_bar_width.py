# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.provisioned_mediaservers import VM
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._storage_locations import SpaceBar
from tests.web_admin._storage_locations import StorageLocations
from vm.networks import setup_flat_network


class test_storage_bar_width(WebAdminTest):
    """Test storage bar width.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84304
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    supplier = ClassicInstallerSupplier(args.distrib_url)
    pool = FTMachinePool(supplier, get_run_dir(), 'v2')
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
    mediaserver_vm = mediaserver_stand.vm()
    [[mediaserver_ip, _], _] = setup_flat_network(
        [mediaserver_vm, browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    main_storage_path = _add_usb_storage(mediaserver_vm, 'Q', 2 * 1024**4)
    inaccessible_storage_path = _add_usb_storage(mediaserver_vm, 'S', 300 * 1024**3)
    backup_storage_path = _add_usb_storage(mediaserver_vm, 'T', 300 * 1024**3)
    reserved_storage_path = _add_usb_storage(mediaserver_vm, 'R', 300 * 1024**3)
    mediaserver = mediaserver_stand.mediaserver()
    mediaserver.start()
    mediaserver_api = mediaserver_stand.api()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    mediaserver_api.setup_local_system()
    local_administrator_credentials = mediaserver_api.get_credentials()
    backup_storage = mediaserver_api.list_storages(str(backup_storage_path))[0]
    mediaserver_api.allocate_storage_for_backup(backup_storage.id)
    mediaserver.stop()
    mediaserver_stand.os_access().dismount_fake_disk(inaccessible_storage_path)
    inaccessible_storage_path.rmtree()
    mediaserver.start()
    default_storage_path = mediaserver.default_archive().storage_root_path()
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_servers_link().invoke()
    storage_locations = StorageLocations(browser)
    available_storages = storage_locations.get_storages_table()
    storages_bar_widths = {}
    for storage_path, storage_entry in available_storages.items():
        space_bar = SpaceBar(storage_entry.get_space())
        bar_width = space_bar.get_width_pixels()
        if storage_path.is_relative_to(main_storage_path):
            _logger.info("MAIN storage found: %s", storage_path)
            storages_bar_widths[str(main_storage_path)] = bar_width
        elif storage_path.is_relative_to(reserved_storage_path):
            _logger.info("RESERVED storage found: %s", storage_path)
            storages_bar_widths[str(reserved_storage_path)] = bar_width
        elif storage_path.is_relative_to(inaccessible_storage_path):
            _logger.info("INACCESSIBLE storage found: %s", storage_path)
            storages_bar_widths[str(inaccessible_storage_path)] = bar_width
        elif storage_path.is_relative_to(backup_storage_path):
            _logger.info("BACKUP storage found: %s", storage_path)
            storages_bar_widths[str(backup_storage_path)] = bar_width
        elif storage_path.is_relative_to(default_storage_path):
            _logger.info("DEFAULT storage found: %s", storage_path)
            storages_bar_widths[str(default_storage_path)] = bar_width
        else:
            raise RuntimeError(f"Unknown storage is found: {storage_path}")
    if len(set(storages_bar_widths.values())) != 1:
        raise AssertionError(f"Bar widths are not the same: {storages_bar_widths}")


def _add_usb_storage(mediaserver_vm: VM, letter: str, size_bytes: int):
    mediaserver_vm.vm_control.add_disk('usb', size_bytes // 1024 // 1024)
    return mediaserver_vm.os_access.mount_disk(letter)


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_storage_bar_width()]))
