# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network
from uuid import UUID

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import StaleElementReference
from browser.webdriver import get_visible_text
from directories import get_run_dir
from distrib import BranchNotSupported
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import MediaserverApi
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.provisioned_mediaservers import VM
from os_access import RemotePath
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._interface_wait import element_is_present
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._nx_apply import NxApplyBar
from tests.web_admin._storage_locations import StorageLocations
from tests.web_admin._storage_locations import storage_mode_choice_menu
from vm.networks import setup_flat_network


class test_main_to_backup(WebAdminTest):
    """Test change storage type.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84326
    See: https://networkoptix.atlassian.net/issues/CLOUD-14707
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    """
    The test is simplified.

    Manual testers do not have easy access to API, so it is difficult for them to check whether
    a storage is in "main" or "backup" mode. Moreover, we already have specific storages tests.
    """
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    if installer_supplier.distrib().older_than('vms_6.0'):
        raise BranchNotSupported(
            "Skipped due to https://networkoptix.atlassian.net/browse/CLOUD-14707")
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
    mediaserver_vm = mediaserver_stand.vm()
    [[mediaserver_ip, _], _] = setup_flat_network(
        [mediaserver_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    mediaserver = mediaserver_stand.mediaserver()
    mediaserver.start()
    mediaserver_api = mediaserver_stand.api()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    mediaserver_api.setup_local_system()
    default_storage = mediaserver_api.list_storages()[0]
    primary_storage, secondary_storage = _add_two_main_storages(mediaserver_vm, mediaserver_api)
    mediaserver_api.disable_storage(default_storage.id)
    primary_storage_type = primary_storage.get_type()
    assert primary_storage_type == _StorageType.main, (
        f"{primary_storage_type!r} != {_StorageType.main!r}"
        )
    secondary_storage_type = secondary_storage.get_type()
    assert secondary_storage_type == _StorageType.main, (
        f"{secondary_storage_type!r} != {_StorageType.main!r}"
        )
    local_administrator_credentials = mediaserver_api.get_credentials()
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    main_menu = MainMenu(browser)
    main_menu.get_servers_link().invoke()
    storage_locations = StorageLocations(browser)
    storages_table = storage_locations.get_storages_table()
    primary_storage_entry = storages_table.find_storage_entry(str(primary_storage.path))
    primary_storage_entry.get_mode().invoke()
    choice_menu = storage_mode_choice_menu(browser, installer_supplier.distrib().version())
    choice_menu.get_backup_entry().choose()
    apply_bar = NxApplyBar(browser)
    assert element_is_present(apply_bar.get_save_button)
    apply_bar.get_cancel_button().invoke()
    assert not element_is_present(apply_bar.get_save_button)
    assert not element_is_present(apply_bar.get_cancel_button)
    primary_storage_type = primary_storage.get_type()
    assert primary_storage_type == _StorageType.main, (
        f"{primary_storage_type!r} != {_StorageType.main!r}"
        )
    secondary_storage_type = secondary_storage.get_type()
    assert secondary_storage_type == _StorageType.main, (
        f"{secondary_storage_type!r} != {_StorageType.main!r}"
        )
    storages_table = storage_locations.get_storages_table()
    primary_storage_entry = storages_table.find_storage_entry(str(primary_storage.path))
    primary_storage_entry.get_mode().invoke()
    choice_menu = storage_mode_choice_menu(browser, installer_supplier.distrib().version())
    choice_menu.get_backup_entry().choose()
    apply_bar.get_save_button().invoke()
    _wait_while_mode_stabilize(browser)
    primary_storage_type = primary_storage.get_type()
    assert primary_storage_type == _StorageType.backup, (
        f"{primary_storage_type!r} != {_StorageType.backup!r}"
        )
    secondary_storage_type = secondary_storage.get_type()
    assert secondary_storage_type == _StorageType.main, (
        f"{secondary_storage_type!r} != {_StorageType.main!r}"
        )


def _add_two_main_storages(
        mediaserver_vm: VM,
        api: MediaserverApi,
        ) -> tuple['_TestStorage', '_TestStorage']:
    primary_storage_path = _add_arbitrary_size_usb_storage(mediaserver_vm, 'Q')
    secondary_storage_path = _add_arbitrary_size_usb_storage(mediaserver_vm, 'R')
    primary_info = api.set_up_new_storage(primary_storage_path)[1]
    primary_storage = _TestStorage(api, primary_info.id, primary_storage_path)
    secondary_info = api.set_up_new_storage(secondary_storage_path)[1]
    secondary_storage = _TestStorage(api, secondary_info.id, secondary_storage_path)
    return primary_storage, secondary_storage


def _add_arbitrary_size_usb_storage(mediaserver_vm: VM, letter: str):
    irrelevant_size_mb = 30 * 1024
    mediaserver_vm.vm_control.add_disk('usb', irrelevant_size_mb)
    return mediaserver_vm.os_access.mount_disk(letter)


def _wait_while_mode_stabilize(browser: Browser):
    intermediate_text = 'Changing mode...'
    selector = ByXPATH.quoted("//span[contains(text(),%s)]", intermediate_text)
    delay = 10
    try:
        intermediate_state = browser.wait_element(selector, delay)
    except ElementNotFound:
        raise RuntimeError(f"Mode didn't change to intermediate value {intermediate_text}")
    end_at = time.monotonic() + delay
    while True:
        try:
            current_text = get_visible_text(intermediate_state)
        except StaleElementReference:
            return
        if current_text != intermediate_text:
            raise RuntimeError(
                "Unexpected logic behaviour. A text MUST NOT change within an element "
                f"without changing it's ID. Received text: {current_text}")
        if end_at < time.monotonic():
            raise RuntimeError(f"Mode didn't change from non-temporary value {current_text}")


class _TestStorage:

    def __init__(self, mediaserver_api: MediaserverApi, uid: UUID, path: RemotePath):
        self._mediaserver_api = mediaserver_api
        self._uid = uid
        self.path = path

    def get_type(self) -> str:
        storage_status = self._mediaserver_api.get_storage(self._uid)
        if storage_status is None:
            raise RuntimeError(f"Can't find storage identified by {self._uid}")
        if storage_status.is_backup:
            return _StorageType.backup
        return _StorageType.main

    def __repr__(self):
        return f'<Storage {self._uid} [{self.path}]>'


class _StorageType:

    main = 'main'
    backup = 'backup'


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_main_to_backup()]))
