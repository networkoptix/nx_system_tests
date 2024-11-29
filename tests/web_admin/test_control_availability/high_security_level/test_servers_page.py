# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import sys
import time
from contextlib import ExitStack
from ipaddress import IPv4Network
from pathlib import PurePosixPath

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import StaleElementReference
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_api import Groups
from mediaserver_api import MediaserverApiV2
from mediaserver_api._mediaserver import SettingsPreset
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from mediaserver_scenarios.storage_preparation import create_smb_share
from os_access import RemotePath
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._information_menu import InformationMenu
from tests.web_admin._interface_wait import assert_elements_absence
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._nx_apply import NxApplyBar
from tests.web_admin._servers import RestartDialogV60Plus
from tests.web_admin._servers import ServerSettings
from tests.web_admin._servers import get_server_name
from tests.web_admin._servers import get_storages_for_analytics
from tests.web_admin._storage_locations import AddExternalStorageDialog
from tests.web_admin._storage_locations import StorageLocations
from tests.web_admin._storage_locations import get_reindex_main_storage_button
from tests.web_admin._storage_locations import wait_storage_added_toast
from tests.web_admin._upper_menu import UpperMenu
from vm.networks import setup_flat_network
from vm.vm import VM


class test_servers_page(WebAdminTest):
    """Security block is hidden for Power User if Security Level is High.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/124000
    """

    def _run(self, args, exit_stack: ExitStack):
        _test_control_availability(args, exit_stack)


def _test_control_availability(args, exit_stack: ExitStack):
    """Covers step 5 from the case."""
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    distrib = installer_supplier.distrib()
    distrib.assert_not_older_than('vms_6.0', "This test is only for VMS 6.0+")
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    smb_vm = exit_stack.enter_context(pool.clean_vm('win11'))
    smb_vm.ensure_started(get_run_dir())
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    mediaserver_vm = mediaserver_stand.vm()
    [[mediaserver_ip, smb_ip, _], _] = setup_flat_network(
        [mediaserver_vm, smb_vm, browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    _add_arbitrary_size_usb_storage(mediaserver_vm, 'Q')
    secondary_storage = _add_arbitrary_size_usb_storage(mediaserver_vm, 'W')
    smb_login = 'UserWithPassword'
    smb_password = 'GoodPassword'
    smb_share_name, smb_path = create_smb_share(
        smb_vm.os_access, smb_login, smb_password, size=10 * 1024**3, letter='P')
    smb_mount_point = mediaserver_vm.os_access.path('/media/smb/')
    smb_mount_point.rmtree(ignore_errors=True)
    mediaserver_vm.os_access.mount_smb_share(
        mount_point=str(smb_mount_point),
        path=f'//{smb_ip}/{smb_share_name}',
        username=smb_login,
        password=smb_password,
        )
    mediaserver_api: MediaserverApiV2 = mediaserver_stand.api()
    mediaserver = mediaserver_stand.mediaserver()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    mediaserver.start()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    mediaserver_api.setup_local_system(
        system_settings={'licenseServer': license_server.url()},
        settings_preset=SettingsPreset.SECURITY,
        )
    mediaserver_api.set_up_new_storage(secondary_storage)
    power_user_name = "power_user"
    power_user_password = "power_user_password"
    mediaserver_api.add_local_user(
        power_user_name, power_user_password, group_id=Groups.POWER_USERS)
    system_name = "Irrelevant_system"
    mediaserver_api.rename_site(system_name)
    camera_server = MultiPartJpegCameraServer()
    add_cameras(mediaserver, camera_server, indices=[0])
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(power_user_name)
    login_form.get_password_field().put(power_user_password)
    login_form.get_submit_button().invoke()
    MainMenu(browser).get_servers_link().invoke()
    StorageLocations(browser).get_detailed_info_button().invoke()
    assert InformationMenu(browser).get_storages_link().is_selected()
    assert '/health/storages' in browser.get_current_url()
    UpperMenu(browser).get_settings_link().invoke()
    MainMenu(browser).get_servers_link().invoke()
    ServerSettings(browser).get_detailed_info_button().invoke()
    assert InformationMenu(browser).get_servers_link().is_selected()
    assert '/health/servers' in browser.get_current_url()
    UpperMenu(browser).get_settings_link().invoke()
    MainMenu(browser).get_servers_link().invoke()
    server_name = "Irrelevant_server"
    editable_name = get_server_name(browser)
    editable_name.set(server_name)
    apply_bar = NxApplyBar(browser)
    assert apply_bar.get_cancel_button().is_active()
    apply_bar.get_save_button().invoke()
    apply_bar.wait_apply()
    server_name_after = editable_name.get_current_value()
    assert server_name_after == server_name, f"{server_name_after!r} != {server_name}"
    _try_find_pencil_icon(browser)
    server_settings = ServerSettings(browser)
    assert_elements_absence(
        server_settings.get_detach_from_system_button,
        server_settings.get_reset_to_defaults_button,
        )
    assert not server_settings.get_port().is_active()
    # The analytics storage change check is disabled due to unstable behavior of
    # the storage dropdown menu. None anchors were found, adding delays doesn't help.
    # storage_dropdown = server_settings.get_analytics_storage_dropdown_button()
    # analytics_storage_before = storage_dropdown.get_text()
    # storage_dropdown.invoke()
    # _change_analytics_storage(browser)
    # apply_bar = NxApplyBar(browser)
    # assert apply_bar.get_cancel_button().is_active()
    # apply_bar.get_save_button().invoke()
    # apply_bar.wait_apply()
    # analytics_storage_after = storage_dropdown.get_text()
    # assert analytics_storage_after != analytics_storage_before, (
    #     f"{analytics_storage_after!r} == {analytics_storage_before!r}"
    #     )
    # See: https://networkoptix.atlassian.net/browse/CLOUD-14434
    smb_address = f'//{smb_ip}/{smb_share_name}'
    first_storage_locations = StorageLocations(browser)
    first_storage_locations.get_add_external_storage_button().invoke()
    add_storage = AddExternalStorageDialog(browser)
    assert add_storage.get_close_button().is_active()
    assert add_storage.get_cancel_button().is_active()
    add_storage.get_url_field().put(smb_address)
    add_storage.get_login_field().put(smb_login)
    add_storage.get_password_field().put(smb_password)
    # Attempt to invoke the "Add Storage" button just after the dialog opening leads to
    # the "Add External Storage" dialog freezing. There are no anchors found inside the dialog
    # itself to ensure it is fully functional
    time.sleep(1)
    add_storage.get_add_storage_button().invoke()
    wait_storage_added_toast(browser, timeout=30)
    _wait_smb_storage_reserved(StorageLocations(browser), str(smb_ip), smb_share_name, timeout=20)
    get_reindex_main_storage_button(browser).invoke()
    _wait_storage_reindexing_complete_toast(browser, timeout=30)
    with mediaserver_api.waiting_for_restart(timeout_sec=30):
        server_settings.get_restart_button().invoke()
        first_restart_dialog = RestartDialogV60Plus(browser)
        assert first_restart_dialog.get_cancel_button().is_active()
        first_restart_dialog.get_restart_button().invoke()


def _wait_smb_storage_reserved(
        storage_location: StorageLocations, smb_ip: str, smb_path: str, timeout: float):
    # It takes some time to a storage to be added via SMB
    end_at = time.monotonic() + timeout
    # SMB Storage path in WebAdmin is represented as Unix path
    smb_unix_path = PurePosixPath('/') / smb_ip / smb_path
    while True:
        try:
            storages_table = storage_location.get_storages_table()
            smb_storage_entry = storages_table.find_storage_entry(smb_unix_path)
            mode = smb_storage_entry.get_mode().get_text()
        except StaleElementReference:
            _logger.debug("Storages list is refreshed while querying")
            continue
        if mode == 'Reserved':
            return
        _logger.debug("SMB storage %s status is not 'Reserved': %r", smb_path, mode)
        if time.monotonic() > end_at:
            raise TimeoutError(
                f"Can't find reserved SMB storage //{smb_ip}/{smb_path} "
                f"amongst {storages_table}")
        time.sleep(0.3)


def _add_arbitrary_size_usb_storage(mediaserver_vm: VM, letter: str) -> RemotePath:
    irrelevant_size_mb = 300 * 1024
    mediaserver_vm.vm_control.add_disk('usb', irrelevant_size_mb)
    return mediaserver_vm.os_access.mount_disk(letter)


def _change_analytics_storage(browser: Browser):
    available_storages = get_storages_for_analytics(browser)
    if len(available_storages) < 2:
        raise RuntimeError("At least two storages should be present")
    for available_storage in available_storages:
        if not available_storage.in_use():
            available_storage.choose()
            return


def _try_find_pencil_icon(browser: Browser):
    icon_selector = ByXPATH("//nx-editable-heading//img[@src='/static/images/icons/edit.png']")
    browser.wait_element(icon_selector, 10)


def _wait_storage_reindexing_complete_toast(browser: Browser, timeout: float):
    xpath = (
        "//nx-app-toasts"
        "//nx-toast"
        "//div["
        "contains(@class, 'alert-success') and contains(., 'Main storage reindexing completed')"
        "]"
        )
    browser.wait_element(ByXPATH(xpath), timeout)


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_servers_page()]))
