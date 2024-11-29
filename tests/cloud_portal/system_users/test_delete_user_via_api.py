# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
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
from vm.networks import setup_flat_network


class test_delete_user_via_api(VMSTest, CloudTest):
    """Test connect system to Cloud via API.

    Selection-Tag: 30727
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_gitlab
    Selection-Tag: cloud_portal_smoke
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/30727
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
        cloud_power_user = exit_stack.enter_context(cloud_account_factory.temp_account())
        mediaserver.api.setup_cloud_system(cloud_owner)
        cloud_power_user_uuid = mediaserver.api.add_cloud_user(
            name=cloud_power_user.user_email,
            email=cloud_power_user.user_email,
            permissions=[Permissions.ADMIN],
            )
        system_id = mediaserver.api.get_cloud_system_id()
        system_name = f'Delete_user_test_system_{int(time.perf_counter_ns())}'
        cloud_owner.rename_system(system_id, system_name)
        browser = exit_stack.enter_context(browser_stand.browser())
        cms_data = get_cms_settings(cloud_host)
        if cms_data.flag_is_enabled('channelPartners'):
            # With the new Channel Partners interface, the only system doesn't open automatically.
            browser.open(f'https://{cloud_host}/systems/{system_id}')
        else:
            browser.open(f'https://{cloud_host}/systems/')
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        # It takes time for the system status to be updated on Cloud portal.
        system_administration_page = SystemAdministrationPage(browser)
        system_administration_page.wait_for_system_name_field(timeout=90)
        time.sleep(30)
        users_dropdown = UsersDropdown(browser)
        users_dropdown.open()
        assert users_dropdown.has_user_with_email(cloud_power_user.user_email)
        mediaserver.api.remove_user(cloud_power_user_uuid)
        browser.refresh()
        users_dropdown.open()
        assert not users_dropdown.has_user_with_email(cloud_power_user.user_email)
        HeaderNav(browser).account_dropdown().invoke()
        AccountDropdownMenu(browser).log_out_option().invoke()
        _wait_for_url(browser, url=f"https://{cloud_host}/")
        browser.open(f'https://{cloud_host}/systems/')
        LoginComponent(browser).login(cloud_power_user.user_email, cloud_power_user.password)
        assert element_is_present(system_administration_page.get_no_systems_text)


def _wait_for_url(browser: Browser, url: str):
    started_at = time.monotonic()
    while True:
        current_url = browser.get_current_url()
        if current_url == url:
            return
        if time.monotonic() - started_at > 10:
            raise RuntimeError(
                f"Wrong location. Expected {url}, got {current_url}")
        time.sleep(0.5)


if __name__ == '__main__':
    exit(test_delete_user_via_api().main())
