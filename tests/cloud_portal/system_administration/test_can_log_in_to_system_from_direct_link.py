# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
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
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._system_tiles import ChannelPartnerSystemTiles
from tests.cloud_portal._system_tiles import SystemTiles
from vm.networks import setup_flat_network


class test_can_log_in_to_system_from_direct_link(VMSTest, CloudTest):
    """Login to Desktop Client by Cloud User.

    Selection-Tag: 143237
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_gitlab
    Selection-Tag: cloud_portal_smoke
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/143237
    """

    def _run(self, args, exit_stack):
        one_vm_type = 'ubuntu22'
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        first_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
        second_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
        cloud_account = exit_stack.enter_context(cloud_account_factory.temp_account())
        additional_cloud_account = exit_stack.enter_context(cloud_account_factory.temp_account())
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_account.set_user_customization(customization_name)
        services_hosts = cloud_account.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [first_stand.vm(), second_stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        first_mediaserver = first_stand.mediaserver()
        first_mediaserver.os_access.cache_dns_in_etc_hosts(
            [cloud_host, *services_hosts, *public_ip_check_addresses])
        first_mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        first_mediaserver.set_cloud_host(cloud_host)
        first_mediaserver.start()
        first_mediaserver.api.setup_cloud_system(cloud_account)
        first_system_id = first_mediaserver.api.get_cloud_system_id()
        second_mediaserver = second_stand.mediaserver()
        second_mediaserver.os_access.cache_dns_in_etc_hosts(
            [cloud_host, *services_hosts, *public_ip_check_addresses])
        second_mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        second_mediaserver.set_cloud_host(cloud_host)
        second_mediaserver.start()
        second_mediaserver.api.setup_cloud_system(additional_cloud_account)
        second_mediaserver.api.add_cloud_user(
            name=cloud_account.user_email,
            email=cloud_account.user_email,
            permissions=[Permissions.ADMIN],
            )
        second_system_id = second_mediaserver.api.get_cloud_system_id()
        home_link = f"https://{cloud_host}/"
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(home_link)
        HeaderNav(browser).get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_account.user_email, cloud_account.password)
        cms_data = get_cms_settings(cloud_host)
        channel_partners_is_enabled = cms_data.flag_is_enabled('channelPartners')
        if channel_partners_is_enabled:
            systems_page = ChannelPartnerSystemTiles(browser)
        else:
            systems_page = SystemTiles(browser)
        systems_page.wait_for_systems_label(timeout=20)
        first_direct_link = f"https://{cloud_host}/systems/{first_system_id}"
        browser.open(first_direct_link)
        system_administration_page = SystemAdministrationPage(browser)
        # Just after user is set up and connected to Cloud system the System Administration page
        # can be loaded with a huge delay.
        timeout = 60.0
        if not _system_administration_page_is_loaded(system_administration_page, timeout=timeout):
            current_url = browser.get_current_url()
            if str(first_system_id) in current_url:
                raise RuntimeError(f"System Administration not loaded after {timeout} seconds")
            else:
                _logger.info(
                    f"Redirected from system {first_system_id} page to {current_url}. Reopening")
                browser.open(first_direct_link)
                system_administration_page.wait_for_system_name_field(timeout)
        assert "Owner – you" in system_administration_page.get_owner_text()
        second_direct_link = f"https://{cloud_host}/systems/{second_system_id}"
        browser.open(second_direct_link)
        # Just after user is set up and connected to Cloud system the System Administration page
        # can be loaded with a huge delay.
        assert _system_administration_page_is_loaded(system_administration_page, timeout=timeout)
        owner_text = system_administration_page.get_owner_text()
        second_account_name = additional_cloud_account.get_user_info().get_full_name()
        assert second_account_name in owner_text, f"{second_account_name} not in {owner_text}"
        assert additional_cloud_account.user_email in owner_text, (
            f"{additional_cloud_account.user_email} not in {owner_text}")


def _system_administration_page_is_loaded(page: SystemAdministrationPage, timeout: float) -> bool:
    try:
        page.wait_for_system_name_field(timeout)
    except ElementNotFound:
        return False
    return True


_logger = logging.getLogger(__name__)


if __name__ == '__main__':
    exit(test_can_log_in_to_system_from_direct_link().main())
