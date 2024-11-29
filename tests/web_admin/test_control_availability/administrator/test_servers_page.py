# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from directories import get_run_dir
from doubles.licensing.local_license_server import LocalLicenseServer
from doubles.software_cameras import MultiPartJpegCameraServer
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_scenarios.merging import merge_systems
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.software_camera_scenarios import add_cameras
from os_access import RemotePath
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._information_menu import InformationMenu
from tests.web_admin._interface_wait import element_is_present
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._nx_apply import NxApplyBar
from tests.web_admin._servers import RestartDialogV60Plus
from tests.web_admin._servers import ServerSettings
from tests.web_admin._servers import get_servers
from tests.web_admin._servers import get_storages_for_analytics
from tests.web_admin._storage_locations import AddExternalStorageDialog
from tests.web_admin._storage_locations import StorageLocations
from tests.web_admin._storage_locations import get_reindex_main_storage_button
from tests.web_admin._upper_menu import UpperMenu
from vm.networks import setup_flat_network
from vm.vm import VM


class test_servers_page(WebAdminTest):
    """Test pages control availability.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/122513
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    """Covers step 5 from the case."""
    installer_supplier = ClassicInstallerSupplier(args.distrib_url)
    installer_supplier.distrib().assert_not_older_than('vms_6.0', "This test is only for VMS 6.0+")
    pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
    one_vm_type = 'ubuntu22'
    first_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    second_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    first_vm = first_stand.vm()
    second_vm = second_stand.vm()
    [[first_mediaserver_ip, _, _], _] = setup_flat_network(
        [first_vm, second_stand.vm(), browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    _add_arbitrary_size_usb_storage(first_vm, 'Q')
    first_vm_secondary_storage = _add_arbitrary_size_usb_storage(first_vm, 'W')
    _add_arbitrary_size_usb_storage(second_vm, 'Q')
    second_vm_secondary_storage = _add_arbitrary_size_usb_storage(second_vm, 'W')
    first_api = first_stand.api()
    first_mediaserver = first_stand.mediaserver()
    second_api = second_stand.api()
    second_mediaserver = second_stand.mediaserver()
    license_server = LocalLicenseServer()
    exit_stack.enter_context(license_server.serving())
    first_mediaserver.start()
    second_mediaserver.start()
    upload_web_admin_to_mediaserver(first_api, args.webadmin_url)
    license_server_url = license_server.url()
    first_api.setup_local_system({'licenseServer': license_server_url})
    second_api.setup_local_system({'licenseServer': license_server_url})
    first_server_name = "first_server"
    second_server_name = "second_server"
    first_api.rename_server(first_server_name)
    second_api.rename_server(second_server_name)
    first_api.set_up_new_storage(first_vm_secondary_storage)
    second_api.set_up_new_storage(second_vm_secondary_storage)
    merge_systems(first_mediaserver, second_mediaserver, take_remote_settings=False)
    local_administrator_credentials = first_api.get_credentials()
    system_name = "Irrelevant_system"
    first_api.rename_site(system_name)
    camera_server = MultiPartJpegCameraServer()
    add_cameras(first_mediaserver, camera_server, indices=[0])
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, first_mediaserver.url(first_mediaserver_ip))
    browser.open(first_mediaserver.url(first_mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    main_menu = MainMenu(browser)
    upper_menu = UpperMenu(browser)
    main_menu.get_servers_link().invoke()
    servers_entries = get_servers(browser)
    assert set(servers_entries.keys()) == {first_server_name, second_server_name}
    first_server_entry = servers_entries[first_server_name]
    second_server_entry = servers_entries[second_server_name]
    apply_bar = NxApplyBar(browser)

    first_server_entry.open()
    assert first_server_entry.is_opened()
    assert not second_server_entry.is_opened()
    _try_find_pencil_icon(browser)
    first_server_settings = ServerSettings(browser)
    assert element_is_present(first_server_settings.get_detach_from_system_button)
    assert element_is_present(first_server_settings.get_reset_to_defaults_button)
    assert first_server_settings.get_port().is_active()
    first_server_settings.get_analytics_storage_dropdown_button().invoke()
    _change_analytics_storage(browser)
    assert apply_bar.get_save_button().is_active()
    apply_bar.get_cancel_button().invoke()
    first_server_settings.get_restart_button().invoke()
    first_restart_dialog = RestartDialogV60Plus(browser)
    assert first_restart_dialog.get_restart_button().is_active()
    first_restart_dialog.get_cancel_button().invoke()
    first_storage_locations = StorageLocations(browser)
    first_storage_locations.get_add_external_storage_button().invoke()
    add_storage_dialog = AddExternalStorageDialog(browser)
    assert add_storage_dialog.get_add_storage_button().is_active()
    add_storage_dialog.get_cancel_button().invoke()
    assert get_reindex_main_storage_button(browser).is_active()
    first_server_settings.get_detailed_info_button().invoke()
    assert InformationMenu(browser).get_servers_link().is_selected()
    assert '/health/servers' in browser.get_current_url()
    upper_menu.get_settings_link().invoke()
    main_menu.get_servers_link().invoke()
    first_server_entry.open()
    try:
        first_storage_locations.get_detailed_info_button().invoke()
    except ElementNotFound as err:
        if 'Detailed Info' in str(err):
            raise RuntimeError(
                "Cannot find Detailed Info button. Storages component may not be found. "
                "See: https://networkoptix.atlassian.net/browse/CLOUD-15300")
        raise
    assert InformationMenu(browser).get_storages_link().is_selected()
    assert '/health/storages' in browser.get_current_url()

    upper_menu.get_settings_link().invoke()
    main_menu.get_servers_link().invoke()
    second_server_entry.open()
    assert second_server_entry.is_opened()
    assert not first_server_entry.is_opened()
    _try_find_pencil_icon(browser)
    second_server_settings = ServerSettings(browser)
    assert element_is_present(second_server_settings.get_detach_from_system_button)
    assert element_is_present(second_server_settings.get_reset_to_defaults_button)
    assert second_server_settings.get_port().is_active()
    second_server_settings.get_analytics_storage_dropdown_button().invoke()
    _change_analytics_storage(browser)
    assert apply_bar.get_save_button().is_active()
    apply_bar.get_cancel_button().invoke()
    second_server_settings.get_restart_button().invoke()
    second_restart_dialog = RestartDialogV60Plus(browser)
    assert second_restart_dialog.get_restart_button().is_active()
    second_restart_dialog.get_cancel_button().invoke()
    second_storage_locations = StorageLocations(browser)
    second_storage_locations.get_add_external_storage_button().invoke()
    add_storage_dialog = AddExternalStorageDialog(browser)
    assert add_storage_dialog.get_add_storage_button().is_active()
    add_storage_dialog.get_cancel_button().invoke()
    assert get_reindex_main_storage_button(browser).is_active()
    second_server_settings.get_detailed_info_button().invoke()
    assert InformationMenu(browser).get_servers_link().is_selected()
    assert '/health/servers' in browser.get_current_url()
    upper_menu.get_settings_link().invoke()
    main_menu.get_servers_link().invoke()
    second_server_entry.open()
    second_storage_locations.get_detailed_info_button().invoke()
    assert InformationMenu(browser).get_storages_link().is_selected()
    assert '/health/storages' in browser.get_current_url()


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


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_servers_page()]))
