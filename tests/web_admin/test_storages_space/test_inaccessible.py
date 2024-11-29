# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
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


class test_inaccessible(WebAdminTest):
    """Test inaccessible storage space.

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
    inaccessible_storage_path = _add_usb_storage(mediaserver_vm, 'S', 300 * 1024**3)
    mediaserver = mediaserver_stand.mediaserver()
    mediaserver.start()
    mediaserver_api = mediaserver_stand.api()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    mediaserver_api.setup_local_system()
    mediaserver_api.set_up_new_storage(inaccessible_storage_path)
    mediaserver.stop()
    mediaserver_stand.os_access().dismount_fake_disk(inaccessible_storage_path)
    inaccessible_storage_path.rmtree()
    mediaserver.start()
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    local_administrator_credentials = mediaserver_api.get_credentials()
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_servers_link().invoke()
    _wait_storages_status_stabilize(browser)
    if supplier.distrib().version().short == (6, 0):
        # In 6.0 the storages table is being re-drawn shortly after the storage status becomes
        # 'Inaccessible' and the status itself does not last for a considerable time.
        # The proper fix implies handling StaleElementReference at every access to the storages
        # table that greatly increases the test complexity. Since in 6.1 this behavior is not
        # observed, the situation being tested is a border case and the issue does not affect
        # an interface user, no JIRA issue is created. A custom-tailored timeout should be enough
        # to decrease the issue occurrence probability below 1%.
        time.sleep(0.75)
    storages_table = StorageLocations(browser).get_storages_table()
    expected_storages_count = 2
    storage_paths = [storage_path for storage_path, _storage_entry in storages_table.items()]
    assert len(storage_paths) == expected_storages_count, (
        f"Not {expected_storages_count} storages are found: {storage_paths}"
        )
    inaccessible_storage_entry = storages_table.find_storage_entry(inaccessible_storage_path)
    mode_element = inaccessible_storage_entry.get_mode()
    mode_text = mode_element.get_text()
    space_bar = SpaceBar(inaccessible_storage_entry.get_space())
    bar_text = space_bar.get_text()
    expected_mode_text = 'Inaccessible'
    assert mode_text == expected_mode_text, f"{mode_text!r} != {expected_mode_text!r}"
    expected_bar_text = "\N{EM DASH}"
    assert bar_text == expected_bar_text, f"{bar_text!r} == {expected_bar_text!r}"
    try:
        legend = space_bar.get_legend(browser)
    except ElementNotFound:
        logging.info("INACCESSIBLE storage %s does not have legend", inaccessible_storage_entry)
    else:
        raise AssertionError(f"INACCESSIBLE storage has legend {legend} but it should not")


def _add_usb_storage(mediaserver_vm: VM, letter: str, size_bytes: int):
    mediaserver_vm.vm_control.add_disk('usb', size_bytes // 1024 // 1024)
    return mediaserver_vm.os_access.mount_disk(letter)


def _wait_storages_status_stabilize(browser: Browser):
    _logger.info("Waiting until inaccessible storage becomes 'Inaccessible' ...")
    _wait_inaccessible(browser, 5)
    _logger.info("Waiting until inaccessible storage becomes 'Checking ...' ... ")
    _wait_checking(browser, 15)
    _logger.info("Waiting until inaccessible storage becomes 'Inaccessible' ...")
    _wait_inaccessible(browser, 60)


def _wait_checking(browser: Browser, timeout: float):
    try:
        browser.wait_element(ByXPATH("//span[contains(text(),'Checking...')]"), timeout)
    except ElementNotFound:
        raise TimeoutError(
            f"Inaccessible storage did not change its status to 'Checking...' after {timeout}")


def _wait_inaccessible(browser: Browser, timeout: float):
    try:
        browser.wait_element(ByXPATH("//div[contains(text(),'Inaccessible')]"), timeout)
    except ElementNotFound:
        raise TimeoutError(
            f"Inaccessible storage did not change its status to 'Inaccessible' after {timeout}")


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_inaccessible()]))
