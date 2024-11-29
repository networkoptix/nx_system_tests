# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ElementNotFound
from cloud_api.cloud import get_cms_settings
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._system_left_menu import UsersDropdown
from tests.cloud_portal._system_users import PermissionsDropdown
from tests.cloud_portal._system_users import SystemUsers
from vm.networks import setup_flat_network


class test_change_role_for_user(VMSTest, CloudTest):
    """Test change user's role.

    Selection-Tag: 41900
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_gitlab
    Selection-Tag: cloud_portal_smoke
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/41900
    """

    def _run(self, args, exit_stack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        server_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        cloud_owner = exit_stack.enter_context(cloud_account_factory.temp_account())
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_owner.set_user_customization(customization_name)
        services_hosts = cloud_owner.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [server_stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver = server_stand.mediaserver()
        mediaserver.os_access.cache_dns_in_etc_hosts(
            [cloud_host, *services_hosts, *public_ip_check_addresses],
            )
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        mediaserver.start()
        mediaserver.api.setup_cloud_system(cloud_owner)
        cloud_viewer = exit_stack.enter_context(cloud_account_factory.temp_account())
        mediaserver.api.add_cloud_user(
            name=cloud_viewer.user_email,
            email=cloud_viewer.user_email,
            permissions=Permissions.VIEWER_PRESET,
            )
        system_id = mediaserver.api.get_cloud_system_id()
        system_name = f'Change_role_for_user_{time.perf_counter_ns()}'
        cloud_owner.rename_system(system_id, system_name)
        browser = exit_stack.enter_context(browser_stand.browser())
        url = f"https://{cloud_host}/systems/{system_id}"
        browser.open(url)
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        SystemAdministrationPage(browser).wait_for_page_to_be_ready()
        users_dropdown = UsersDropdown(browser)
        users_dropdown.open()
        users_dropdown.get_user_with_email(cloud_viewer.user_email).invoke()
        permissions_dropdown = PermissionsDropdown(browser)
        permissions_dropdown.get_permissions_dropdown_button().invoke()
        if installer_supplier.distrib().newer_than("vms_5.1"):
            viewers_option = permissions_dropdown.get_viewer_6x_option()
            assert viewers_option.is_selected()
            power_user_option = permissions_dropdown.get_power_users_option()
            assert not power_user_option.is_selected()
            power_user_option.select()
            permissions_dropdown.get_permissions_dropdown_button().invoke()
            viewers_option.unselect()
        else:
            try:
                viewers_option = permissions_dropdown.get_viewer_51_option()
            except ElementNotFound:
                raise AssertionError(
                    "Cannot find the Viewer role among the permissions, "
                    "probably because of the bug: User roles are in the plural. "
                    "See: https://networkoptix.atlassian.net/browse/CLOUD-14665")
            assert viewers_option.is_selected()
            admin_option = permissions_dropdown.get_administrator_option()
            admin_option.select()
        system_users = SystemUsers(browser)
        system_users.save_button().invoke()
        assert element_is_present(system_users.no_unsaved_changes)
        user_role = PermissionsDropdown(browser).get_permissions_dropdown_text()
        if installer_supplier.distrib().newer_than("vms_5.1"):
            assert "Power Users" in user_role
        else:
            assert "Administrator" in user_role
        # The extra steps below are not part of the TestRail test but are added to
        # validate that the user truly changed from a Viewer to a Power User / Administrator.
        header = HeaderNav(browser)
        header.account_dropdown().invoke()
        AccountDropdownMenu(browser).log_out_option().invoke()
        _wait_for_correct_location(browser, url=f"https://{cloud_host}/", timeout=10)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_viewer.user_email, cloud_viewer.password)
        cms_data = get_cms_settings(cloud_host)
        if cms_data.flag_is_enabled('channelPartners'):
            # With the new Channel Partners interface, the only system doesn't open automatically.
            _wait_for_correct_location(browser, f'https://{cloud_host}/home/shared', timeout=10)
            browser.open(url)
        users_dropdown = UsersDropdown(browser)
        users_dropdown.open()
        users_dropdown.get_user_with_email(cloud_viewer.user_email).invoke()
        assert not element_is_present(SystemUsers(browser).remove_user_button)
        assert not element_is_present(PermissionsDropdown(browser).get_permissions_dropdown_button)


def _wait_for_correct_location(browser: Browser, url: str, timeout: float):
    started_at = time.monotonic()
    while True:
        current_url = browser.get_current_url()
        if current_url == url:
            return
        if time.monotonic() - started_at > timeout:
            raise RuntimeError(
                f"Wrong location. Expected {url}, got {current_url}")
        time.sleep(0.5)


if __name__ == '__main__':
    exit(test_change_role_for_user().main())
