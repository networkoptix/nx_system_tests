# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import sys
from contextlib import ExitStack
from ipaddress import IPv4Network
from xml.etree.ElementTree import Element
from xml.etree.ElementTree import XML

from browser.chrome.provisioned_chrome import chrome_stand
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import upload_web_admin_to_mediaserver
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from mediaserver_scenarios.provisioned_mediaservers import VM
from mediaserver_scenarios.storage_preparation import create_smb_share
from os_access import OsAccess
from os_access import RemotePath
from runner.ft_test import run_ft_test
from tests.base_test import WebAdminTest
from tests.web_admin._collect_version import collect_version
from tests.web_admin._login import LoginForm
from tests.web_admin._main_menu import MainMenu
from tests.web_admin._storage_locations import IconType
from tests.web_admin._storage_locations import StorageLocations
from vm.networks import setup_flat_network


class test_local_owner(WebAdminTest):
    """Test storages icons.

    Selection-Tag: web-admin-gitlab
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/84282
    """

    def _run(self, args, exit_stack: ExitStack):
        _test(args, exit_stack)


def _test(args, exit_stack: ExitStack):
    # The original test implies test network icons from different independent users.
    # It is split to several ones to achieve better granularity and reliability.
    browser_stand = exit_stack.enter_context(chrome_stand([]))
    supplier = ClassicInstallerSupplier(args.distrib_url)
    pool = FTMachinePool(supplier, get_run_dir(), 'v2')
    mediaserver_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
    smb_vm = exit_stack.enter_context(pool.clean_vm('win11'))
    smb_vm.ensure_started(get_run_dir())
    [[mediaserver_ip, smb_ip, _], _] = setup_flat_network(
        [mediaserver_stand.vm(), smb_vm, browser_stand.vm()],
        IPv4Network('10.254.10.0/28'),
        )
    mediaserver_api = mediaserver_stand.api()
    usb_storage_path = _add_usb_storage(mediaserver_stand.vm(), 32 * 1024**3)
    smb_storage_path = _add_smb_storage(
        mediaserver_stand.os_access(), smb_vm.os_access, smb_ip, 300 * 1024**3)
    mediaserver = mediaserver_stand.mediaserver()
    mediaserver.start()
    upload_web_admin_to_mediaserver(mediaserver_api, args.webadmin_url)
    mediaserver_api.setup_local_system()
    local_storage_path = mediaserver_stand.mediaserver().default_archive().storage_root_path()
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
    storages_table = StorageLocations(browser).get_storages_table()
    expected_storages_count = 3
    storage_paths = [storage_path for storage_path, _storage_entry in storages_table.items()]
    assert len(storage_paths) == expected_storages_count, (
        f"Not {expected_storages_count} storages are found: {storage_paths}"
        )

    local_storage_entry = storages_table.find_storage_entry(local_storage_path)
    local_storage_icon = local_storage_entry.get_icon()
    local_storage_icon_type = local_storage_icon.type()
    local_storage_svg_icon_text = local_storage_icon.svg()
    assert local_storage_icon_type == IconType.LOCAL, (
        f"{local_storage_icon_type!r} != {IconType.LOCAL!r}"
        )
    assert _svg_is_not_empty(local_storage_svg_icon_text)

    usb_storage_entry = storages_table.find_storage_entry(usb_storage_path)
    usb_storage_icon = usb_storage_entry.get_icon()
    usb_storage_icon_type = usb_storage_icon.type()
    usb_storage_svg_icon_text = usb_storage_icon.svg()
    assert usb_storage_icon_type == IconType.USB, (
        f"{usb_storage_icon_type!r} != {IconType.USB!r}"
        )
    assert _svg_is_not_empty(usb_storage_svg_icon_text)

    network_storage_entry = storages_table.find_storage_entry(smb_storage_path)
    network_storage_icon = network_storage_entry.get_icon()
    network_storage_icon_type = network_storage_icon.type()
    network_storage_svg_icon_text = network_storage_icon.svg()
    assert network_storage_icon_type == IconType.NETWORK, (
        f"{network_storage_icon_type!r} != {IconType.NETWORK!r}"
        )
    assert _svg_is_not_empty(network_storage_svg_icon_text)


def _add_usb_storage(mediaserver_vm: VM, size_bytes: int) -> RemotePath:
    mediaserver_vm.vm_control.add_disk('usb', size_bytes // 1024 // 1024)
    return mediaserver_vm.os_access.mount_disk('Q')


def _add_smb_storage(
        mediaserver_access: OsAccess,
        smb_access: OsAccess,
        smb_address: str,
        size_bytes: int,
        ) -> RemotePath:
    smb_login = 'UserWithPassword'
    smb_password = 'GoodPassword'
    smb_share_name, smb_path = create_smb_share(
        smb_access,
        smb_login,
        smb_password,
        size_bytes,
        'P',
        )
    smb_mount_point = mediaserver_access.path('/media/smb/')
    smb_mount_point.rmtree(ignore_errors=True)
    mediaserver_access.mount_smb_share(
        mount_point=str(smb_mount_point),
        path=f'//{smb_address}/{smb_share_name}',
        username=smb_login,
        password=smb_password,
        )
    return smb_mount_point


def _svg_is_not_empty(svg_text: str) -> bool:
    namespaces = {'svg': 'http://www.w3.org/2000/svg'}
    svg: Element = XML(svg_text)
    return len(svg.findall('svg:path', namespaces)) > 0


if __name__ == '__main__':
    exit(run_ft_test(sys.argv, [test_local_owner()]))
