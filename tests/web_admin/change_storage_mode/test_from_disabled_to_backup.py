# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import StaleElementReference
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
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._nx_apply import NxApplyBar
from tests.web_admin._storage_locations import StorageLocations
from tests.web_admin._storage_locations import storage_mode_choice_menu
from vm.networks import setup_flat_network
from vm.vm import VM


class test_from_disabled_to_backup(WebAdminTest):
    """Change storage mode from "Not in use" to "Backup".

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84328
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    if installer_supplier.distrib().older_than('vms_6.0'):
        raise BranchNotSupported(
            "Skipped due to https://networkoptix.atlassian.net/browse/CLOUD-14707")
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
    mediaserver_vm = mediaserver_stand.vm()
    [[mediaserver_ip, _], _] = setup_flat_network(
        [mediaserver_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    disabled_storage_path = str(_add_usb_storage(mediaserver_vm, 'T', 300 * 1024**3))
    mediaserver: Mediaserver = mediaserver_stand.mediaserver()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    mediaserver.start()
    mediaserver_api: MediaserverApiV2 = mediaserver_stand.api()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    brand = mediaserver_api.get_brand()
    license_key = license_server.generate({'QUANTITY2': 1, 'BRAND2': brand})
    mediaserver_api.setup_local_system({'licenseServer': license_server.url()})
    mediaserver_api.activate_license(license_key)
    camera_server = MultiPartJpegCameraServer()
    single_camera = add_cameras(mediaserver, camera_server, indices=[0])[0]
    local_administrator_credentials = mediaserver_api.get_credentials()
    _discovered, disabled_storage = mediaserver_api.set_up_new_storage(
        disabled_storage_path, is_backup=True)
    mediaserver_api.disable_storage(disabled_storage.id)
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_servers_link().invoke()
    main_storage_path = mediaserver.default_archive().storage_root_path()
    main_archive = mediaserver.archive(main_storage_path)
    camera_main_archive = main_archive.camera_archive(single_camera.physical_id)
    disabled_archive = mediaserver.archive(disabled_storage.path)
    camera_disabled_archive = disabled_archive.camera_archive(single_camera.physical_id)
    with mediaserver_api.camera_recording(single_camera.id):
        camera_server.serve(time_limit_sec=10)
    main_periods = camera_main_archive.high().list_periods()
    disabled_periods = camera_disabled_archive.high().list_periods()
    assert len(main_periods) == 1, f"Main: {main_periods}, Disabled: {disabled_periods}"
    assert len(disabled_periods) == 0, f"Main: {main_periods}, Disabled: {disabled_periods}"
    storages_table = StorageLocations(browser).get_storages_table()
    disabled_storage_entry = storages_table.find_storage_entry(disabled_storage_path)
    disabled_storage_entry.get_mode().invoke()
    choice_menu = storage_mode_choice_menu(browser, installer_supplier.distrib().version())
    choice_menu.get_backup_entry().choose()
    NxApplyBar(browser).get_save_button().invoke()
    mediaserver_api.enable_backup_for_cameras([single_camera.id])
    _wait_archives_sync(camera_main_archive.high(), camera_disabled_archive.high(), timeout=10)


def _add_usb_storage(mediaserver_vm: VM, letter: str, size_bytes: int):
    mediaserver_vm.vm_control.add_disk('usb', size_bytes // 1024 // 1024)
    return mediaserver_vm.os_access.mount_disk(letter)


def _wait_storage_become_backup(
        storage_locations: StorageLocations, examined_storage_path: str, timeout: float):
    end_at = time.monotonic() + timeout
    while True:
        try:
            storages_table = storage_locations.get_storages_table()
            storage_entry = storages_table.find_storage_entry(examined_storage_path)
            if storage_entry.get_mode().get_text() == 'Backup':
                return
        except StaleElementReference:
            _logger.info("A table or one of its elements has been renewed. Try again")
            continue
        if end_at < time.monotonic():
            raise RuntimeError("Storage mode has not changed to Main")
        time.sleep(0.5)


def _wait_archives_sync(source: VideoArchive, destination: VideoArchive, timeout: float):
    end_at = time.monotonic() + timeout
    while True:
        source_periods = source.list_periods()
        destination_periods = destination.list_periods()
        if len(source_periods) == len(destination_periods):
            return
        if time.monotonic() > end_at:
            raise RuntimeError(
                f"Archives sequences are different after {timeout} sec: "
                f"Source {source_periods}, Destination {destination_periods}")
        time.sleep(0.5)


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_from_disabled_to_backup()]))
