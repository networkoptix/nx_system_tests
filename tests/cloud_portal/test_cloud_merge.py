# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import ElementNotFound
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import Groups
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._system_left_menu import SystemLeftMenu
from tests.cloud_portal._system_left_menu import UsersDropdown
from vm.networks import setup_flat_network


class test_cloud_merge(VMSTest, CloudTest):
    """Test merge from primary system.

    Selection-Tag: 70930
    Selection-Tag: 78231
    Selection-Tag: cloud_portal
    Selection-Tag: unstable
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/70930
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/78231
    Unstable because of: https://networkoptix.atlassian.net/browse/FT-2405
    """

    def _run(self, args, exit_stack):
        one_vm_type = 'ubuntu22'
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v3')
        first_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
        second_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
        cloud_account = cloud_account_factory.create_account()
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_account.set_user_customization(customization_name)
        services_hosts = cloud_account.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [first_stand.vm(), second_stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        first_api = first_stand.api()
        first_mediaserver = first_stand.mediaserver()
        first_mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        first_mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        first_mediaserver.set_cloud_host(cloud_host)
        second_api = second_stand.api()
        second_mediaserver = second_stand.mediaserver()
        first_mediaserver.start()
        first_server_name = "First server"
        first_api.rename_server(first_server_name)
        [first_camera] = first_api.add_test_cameras(0, 1)
        first_mediaserver.api.setup_cloud_system(cloud_account)
        cloud_viewer_first = cloud_account_factory.create_account()
        cloud_viewer_first.set_user_customization(customization_name)
        first_mediaserver.api.add_cloud_user(
            name=cloud_viewer_first.user_email,
            email=cloud_viewer_first.user_email,
            group_id=Groups.VIEWERS,
            )
        second_mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        second_mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        second_mediaserver.set_cloud_host(cloud_host)
        second_mediaserver.start()
        second_server_name = "Second server"
        second_api.rename_server(second_server_name)
        [second_camera] = second_api.add_test_cameras(1, 1)
        first_system_id = first_mediaserver.api.get_cloud_system_id()
        second_mediaserver.api.setup_cloud_system(cloud_account)
        first_system_name = f'Tile_first_system_{int(time.perf_counter_ns())}'
        cloud_account.rename_system(first_system_id, first_system_name)
        second_system_id = second_mediaserver.api.get_cloud_system_id()
        second_system_name = f'Tile_second_system_{int(time.perf_counter_ns())}'
        cloud_account.rename_system(second_system_id, second_system_name)
        cloud_viewer_second = cloud_account_factory.create_account()
        cloud_viewer_second.set_user_customization(customization_name)
        second_mediaserver.api.add_cloud_user(
            name=cloud_viewer_second.user_email,
            email=cloud_viewer_second.user_email,
            group_id=Groups.VIEWERS,
            )
        browser = exit_stack.enter_context(browser_stand.browser())
        link = f"https://{cloud_host}/systems/{first_mediaserver.api.get_cloud_system_id()}"
        browser.open(link)

        LoginComponent(browser).login(cloud_account.user_email, cloud_account.password)
        sys_admin = SystemAdministrationPage(browser)
        _system_admin_page_is_loaded(sys_admin, timeout=40)
        sys_admin.get_merge_with_another_system_button().invoke()
        # Sometimes "Some of the servers have an outdated software version" appears instead of systems list.
        # See: https://networkoptix.atlassian.net/browse/FT-2405
        sys_admin.ensure_system_online(second_mediaserver.api.get_system_name(), timeout=20)
        sys_admin.primary_first_system()
        sys_admin.get_merge_next_button().invoke()
        # TODO: Introduce mechanics to kill the current session.
        sys_admin.get_merge_systems_button().invoke()
        # TODO: Figure out how to grab the yellow banner every time it appears.
        # Sometimes the yellow banner appears too fast and is not captured, so the test fails.
        sys_admin.wait_for_systems_merged_success_toast_notification(
            first_system_name,
            second_system_name,
            )
        browser.refresh()
        users_dropdown = UsersDropdown(browser)
        users_dropdown.open()
        users_dropdown.get_user_with_email(cloud_viewer_first.user_email)
        users_dropdown.get_user_with_email(cloud_viewer_second.user_email)
        left_menu = SystemLeftMenu(browser)
        left_menu.wait_until_visible()
        left_menu.open_servers()
        left_menu.wait_for_server_with_name(first_server_name)
        left_menu.wait_for_server_with_name(second_server_name)
        left_menu.open_cameras()
        left_menu.wait_for_camera_with_name(first_camera.name)
        left_menu.wait_for_camera_with_name(second_camera.name)
        browser.open(f"https://{cloud_host}/systems/")
        # As now owner has only one system, it is automatically open after proceeding to /systems.
        assert _system_admin_page_is_loaded(sys_admin, timeout=20)


def _system_admin_page_is_loaded(system_admin: SystemAdministrationPage, timeout: float) -> bool:
    try:
        system_admin.wait_for_system_name_field(timeout)
    except ElementNotFound:
        return False
    return True


if __name__ == '__main__':
    exit(test_cloud_merge().main())
