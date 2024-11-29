# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.css_properties import get_text_color
from browser.nx_colors import ERROR_RED
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import StaleElementReference
from browser.webdriver import VisibleElement
from browser.webdriver import WebDriverElement
from directories import get_run_dir
from distrib import BranchNotSupported
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import Mediaserver
from installation import VideoArchive
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import MediaserverApiV2
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.provisioned_mediaservers import VM
from mediaserver_scenarios.software_camera_scenarios import add_cameras
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


class test_main_to_not_in_use(WebAdminTest):
    """Change storage mode from Main to Not in use.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84330
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    """
    The test is simplified.

    Users are not added because they are not used in this test.
    """
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    if installer_supplier.distrib().older_than('vms_6.0'):
        raise BranchNotSupported(
            "Skipped due to https://networkoptix.atlassian.net/browse/CLOUD-14707")
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
    mediaserver_vm = mediaserver_stand.vm()
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    [[mediaserver_ip, _], _] = setup_flat_network(
        [mediaserver_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    secondary_storage_path = str(_add_usb_storage(mediaserver_vm, 'T', 30 * 1024**3))
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    mediaserver: Mediaserver = mediaserver_stand.mediaserver()
    mediafile_duration = 5
    mediaserver.update_conf({'mediaFileDuration': mediafile_duration})
    mediaserver.start()
    mediaserver_api: MediaserverApiV2 = mediaserver_stand.api()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    brand = mediaserver_api.get_brand()
    license_key = license_server.generate({'QUANTITY2': 1, 'BRAND2': brand})
    mediaserver_api.setup_local_system({'licenseServer': license_server.url()})
    mediaserver_api.activate_license(license_key)
    camera_server = MultiPartJpegCameraServer()
    [single_camera] = add_cameras(mediaserver, camera_server, indices=[0])
    _discovered, secondary_saved = mediaserver_api.set_up_new_storage(secondary_storage_path)
    primary_storage_path = mediaserver.default_archive().storage_root_path()
    primary_archive = mediaserver.archive(primary_storage_path)
    camera_primary_archive = primary_archive.camera_archive(single_camera.physical_id).high()
    secondary_archive = mediaserver.archive(secondary_saved.path)
    camera_secondary_archive = secondary_archive.camera_archive(single_camera.physical_id).high()
    exit_stack.enter_context(camera_server.async_serve())
    mediaserver_api.start_recording(single_camera.id)
    _wait_non_empty(
        camera_primary_archive, camera_secondary_archive, timeout=mediafile_duration * 5)
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
    primary_storage_entry = storages_table.find_storage_entry(primary_storage_path)
    primary_storage_entry.get_mode().invoke()
    choice_menu = storage_mode_choice_menu(browser, installer_supplier.distrib().version())
    choice_menu.get_not_in_use_entry().choose()
    alert_badge = _get_recording_stop_alert_badge(browser)
    color = get_text_color(alert_badge)
    assert color.is_close_to(ERROR_RED), f"{color!r} is far from {ERROR_RED!r}"
    NxApplyBar(browser).get_save_button().invoke()
    warning_icon = _get_warning_icon(StorageLocations(browser), primary_storage_path, timeout=10)
    icon_center = warning_icon.get_bounding_rect().get_absolute_coordinates(0.5, 0.5)
    browser.request_mouse().hover(icon_center)
    assert element_is_present(lambda: _get_stopped_recording_warning(browser))
    _wait_completed(camera_primary_archive, timeout=mediafile_duration * 3)
    _wait_active(camera_secondary_archive, timeout=mediafile_duration * 3)


def _add_usb_storage(mediaserver_vm: VM, letter: str, size_bytes: int):
    mediaserver_vm.vm_control.add_disk('usb', size_bytes // 1024 // 1024)
    return mediaserver_vm.os_access.mount_disk(letter)


def _wait_completed(archive: VideoArchive, timeout: float):
    end_at = time.monotonic() + timeout
    while True:
        last_period = archive.list_periods()[-1]
        if last_period.complete:
            return
        if time.monotonic() > end_at:
            raise RuntimeError(f"{archive} is not completed after {timeout} sec")
        time.sleep(0.5)


def _wait_active(archive: VideoArchive, timeout: float):
    end_at = time.monotonic() + timeout
    while True:
        last_period = archive.list_periods()[-1]
        if not last_period.complete:
            return
        if time.monotonic() > end_at:
            raise RuntimeError(f"{archive} is not finished after {timeout} sec")
        time.sleep(0.5)


def _wait_non_empty(*archives: VideoArchive, timeout: float):
    end_at = time.monotonic() + timeout
    while True:
        for archive in archives:
            if not archive.list_periods():
                if time.monotonic() > end_at:
                    raise RuntimeError(f"{archive} is empty after {timeout} sec")
                time.sleep(1)
                break
        else:
            return


def _get_recording_stop_alert_badge(browser: Browser) -> WebDriverElement:
    warning_text = (
        'Recording to this storage location will stop. '
        'However, outdated footage from it will continue being deleted.'
        )
    xpath_template = "//nx-apply//div[contains(., %s) and contains(@class, 'warning-text')]"
    selector = ByXPATH.quoted(xpath_template, warning_text)
    return browser.wait_element(selector, 10)


def _get_warning_icon(
        storage_location: StorageLocations, storage_path: str, timeout: float) -> VisibleElement:
    end_at = time.monotonic() + timeout
    while True:
        try:  # A table may go through a temporary state which is difficult to catch properly.
            storages_table = storage_location.get_storages_table()
            main_storage_entry = storages_table.find_storage_entry(storage_path)
            main_storage_entry.get_mode().invoke()
        except StaleElementReference:
            _logger.info("Table is changed while queried. Re-query it without a delay")
            continue
        try:
            return main_storage_entry.get_mode().get_warning_icon()
        except (ElementNotFound, StaleElementReference):
            if time.monotonic() > end_at:
                raise RuntimeError(f"Warning icon did not appear after {timeout} sec")
            time.sleep(0.5)


def _get_stopped_recording_warning(browser: Browser) -> WebDriverElement:
    warning_text = (
        'Recording to this storage location is stopped. '
        'However, outdated footage from it is still being deleted.'
        )
    warning_selector = ByXPATH.quoted("//*[contains(text(), %s)]", warning_text)
    return browser.wait_element(warning_selector, 10)


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_main_to_not_in_use()]))
