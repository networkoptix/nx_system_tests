# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from directories import get_run_dir
from distrib import BranchNotSupported
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


class test_reserved(WebAdminTest):
    """Test reserved storage space.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84304
    See: https://networkoptix.atlassian.net/browse/CLOUD-13152
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    if installer_supplier.distrib().newer_than('vms_5.1'):
        error_message = (
            "Skipped until changes from https://networkoptix.atlassian.net/browse/CLOUD-13152"
            "are cherry-picked to every branch. The test is to be refactored then"
            )
        raise BranchNotSupported(error_message)
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
    mediaserver_vm = mediaserver_stand.vm()
    [[mediaserver_ip, _], _] = setup_flat_network(
        [mediaserver_vm, browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    _add_usb_storage(mediaserver_vm, 'Q', 300 * 1024**3)
    reserved_storage_path = _add_usb_storage(mediaserver_vm, 'X', 20 * 1024**3)
    mediaserver = mediaserver_stand.mediaserver()
    mediaserver.start()
    mediaserver_api = mediaserver_stand.api()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    mediaserver_api.setup_local_system()
    local_administrator_credentials = mediaserver_api.get_credentials()
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_servers_link().invoke()
    storages_table = StorageLocations(browser).get_storages_table()
    expected_storages_count = 2
    storage_paths = [storage_path for storage_path, _storage_entry in storages_table.items()]
    assert len(storage_paths) == expected_storages_count, (
        f"Not {expected_storages_count} storages are found: {storage_paths}"
        )
    reserved_storage_entry = storages_table.find_storage_entry(reserved_storage_path)
    mode_element = reserved_storage_entry.get_mode()
    mode_text = mode_element.get_text()
    space_bar = SpaceBar(reserved_storage_entry.get_space())
    bar_text = space_bar.get_text()
    expected_mode_text = 'Reserved'
    assert mode_text == expected_mode_text, f"{mode_text!r} != {expected_mode_text!r}"
    expected_bar_text = '19.5 GB'
    assert bar_text == expected_bar_text, f"{bar_text!r} != {expected_bar_text!r}"
    expected_spaces = {
        'Size': bar_text,
        'Other data': '1.0 GB',
        'VMS': "\N{EM DASH}",
        'Reserved': '10.0 GB',
        'Available': '8.5 GB',
        }
    spaces_by_name = space_bar.get_legend(browser).get_spaces()
    assert spaces_by_name == expected_spaces, f"{spaces_by_name} != {expected_spaces}"


def _add_usb_storage(mediaserver_vm: VM, letter: str, size_bytes: int):
    mediaserver_vm.vm_control.add_disk('usb', size_bytes // 1024 // 1024)
    return mediaserver_vm.os_access.mount_disk(letter)


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_reserved()]))
