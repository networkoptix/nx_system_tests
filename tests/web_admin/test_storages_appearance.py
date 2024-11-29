# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.color import RGBColor
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.provisioned_mediaservers import VM
from os_access import RemotePath
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._interface_wait import element_is_present
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._storage_locations import StorageLocations
from vm.networks import setup_flat_network


class test_storages_appearance(WebAdminTest):
    """Test storages appearance.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/85459
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
    mediaserver = mediaserver_stand.mediaserver()
    mediaserver.start()
    mediaserver_api = mediaserver_stand.api()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    mediaserver_api.setup_local_system()
    main_storage_path = _add_arbitrary_size_usb_storage(mediaserver_vm, 'Q')
    inaccessible_storage_path = _add_arbitrary_size_usb_storage(mediaserver_vm, 'S')
    # The inaccessible storage disappears if it's not added explicitly.
    mediaserver_api.set_up_new_storage(inaccessible_storage_path)
    disabled_storage_path = _add_arbitrary_size_usb_storage(mediaserver_vm, 'T')
    # If not added explicitly, the disabled storage status differs across versions.
    # In 5.1 it's "Not in use". In 6.0, it's "Reserved".
    mediaserver_api.set_up_new_storage(disabled_storage_path)
    local_administrator_credentials = mediaserver_api.get_credentials()
    disabled_storage = mediaserver_api.list_storages(str(disabled_storage_path))[0]
    mediaserver_api.disable_storage(disabled_storage.id)
    mediaserver.stop()
    mediaserver_stand.os_access().dismount_fake_disk(inaccessible_storage_path)
    inaccessible_storage_path.rmtree()
    mediaserver.start()
    default_storage_path = mediaserver_stand.mediaserver().default_archive().storage_root_path()
    browser = exit_stack.enter_context(browser_stand.browser())
    collect_version(browser, mediaserver.url(mediaserver_ip))
    browser.open(mediaserver.url(mediaserver_ip))
    login_form = LoginForm(browser)
    login_form.get_login_field().put(local_administrator_credentials.username)
    login_form.get_password_field().put(local_administrator_credentials.password)
    login_form.get_submit_button().invoke()
    main_menu = MainMenu(browser)
    main_menu.get_servers_link().invoke()
    enabled_storage_color = RGBColor(43, 56, 63)
    disabled_storage_color = RGBColor(185, 199, 206)
    inaccessible_storage_color = RGBColor(220, 44, 44)
    storage_locations = StorageLocations(browser)
    storages_table = storage_locations.get_storages_table()
    expected_storages_count = 4
    storage_paths = [storage_path for storage_path, _storage_entry in storages_table.items()]
    assert len(storage_paths) == expected_storages_count, (
        f"Not {expected_storages_count} storages are found: {storage_paths}"
        )

    main_storage_entry = storages_table.find_storage_entry(main_storage_path)
    main_mode_element = main_storage_entry.get_mode()
    main_storage_mode_text = main_mode_element.get_text()
    main_storage_text_color = main_mode_element.get_text_color()
    expected_main_storage_mode_text = 'Main'
    assert main_storage_mode_text == expected_main_storage_mode_text, (
        f"{main_storage_mode_text!r} != {expected_main_storage_mode_text!r}"
        )
    assert main_storage_text_color.is_shade_of(enabled_storage_color), (
        f"{main_storage_text_color!r} != {enabled_storage_color}"
        )
    assert element_is_present(main_mode_element.get_dropdown), (
        f"{expected_main_storage_mode_text!r} lacks mode choice menu dropdown"
        )

    # Default storage automatically gets disabled when a bigger storage appears.
    reserved_storage_entry = storages_table.find_storage_entry(default_storage_path)
    reserved_mode_element = reserved_storage_entry.get_mode()
    reserved_storage_mode_text = reserved_mode_element.get_text()
    reserved_storage_text_color = reserved_mode_element.get_text_color()
    expected_reserved_storage_mode = 'Reserved'
    assert reserved_storage_mode_text == expected_reserved_storage_mode, (
        f"{reserved_storage_mode_text!r} != {expected_reserved_storage_mode!r}"
        )
    assert reserved_storage_text_color.is_shade_of(disabled_storage_color), (
        f"{reserved_storage_text_color!r} != {disabled_storage_color}"
        )

    inaccessible_storage_entry = storages_table.find_storage_entry(inaccessible_storage_path)
    inaccessible_mode_element = inaccessible_storage_entry.get_mode()
    inaccessible_storage_mode_text = inaccessible_mode_element.get_text()
    inaccessible_storage_text_color = inaccessible_mode_element.get_text_color()
    expected_inaccessible_storage_mode = 'Inaccessible'
    assert inaccessible_storage_mode_text == expected_inaccessible_storage_mode, (
        f"{inaccessible_storage_mode_text!r} != {expected_inaccessible_storage_mode!r}"
        )
    assert inaccessible_storage_text_color.is_shade_of(inaccessible_storage_color), (
        f"{inaccessible_storage_text_color!r} != {inaccessible_storage_color}"
        )

    disabled_storage_entry = storages_table.find_storage_entry(disabled_storage_path)
    disabled_mode_element = disabled_storage_entry.get_mode()
    disabled_storage_mode_text = disabled_mode_element.get_text()
    disabled_storage_text_color = disabled_mode_element.get_text_color()
    expected_disabled_storage_mode = 'Not in use'
    assert disabled_storage_mode_text == expected_disabled_storage_mode, (
        f"{disabled_storage_mode_text!r} != {expected_disabled_storage_mode!r}"
        )
    assert disabled_storage_text_color.is_shade_of(enabled_storage_color), (
        f"{disabled_storage_text_color!r} != {enabled_storage_color}"
        )
    assert element_is_present(disabled_mode_element.get_dropdown), (
        f"{expected_disabled_storage_mode!r} lacks mode choice menu dropdown"
        )


def _add_arbitrary_size_usb_storage(mediaserver_vm: VM, letter: str) -> RemotePath:
    irrelevant_size_mb = 300 * 1024
    mediaserver_vm.vm_control.add_disk('usb', irrelevant_size_mb)
    return mediaserver_vm.os_access.mount_disk(letter)


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_storages_appearance()]))
