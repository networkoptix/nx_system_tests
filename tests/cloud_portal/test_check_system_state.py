# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import ElementNotFound
from cloud_api.cloud import get_cms_settings
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._system_tiles import ChannelPartnerSystemTiles
from tests.cloud_portal._system_tiles import SystemTiles
from vm.networks import setup_flat_network


class test_check_system_state(VMSTest, CloudTest):
    """Test check system state.

    Selection-Tag: 30826
    Selection-Tag: cloud_portal
    Selection-Tag: unstable
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30826
    """

    def _run(self, args, exit_stack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        platform = 'ubuntu22'
        first_stand = exit_stack.enter_context(pool.one_mediaserver(platform))
        second_stand = exit_stack.enter_context(pool.one_mediaserver(platform))
        cloud_account = cloud_account_factory.create_account()
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_account.set_user_customization(customization_name)
        services_hosts = cloud_account.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [first_stand.vm(), second_stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver = first_stand.mediaserver()
        mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        mediaserver.start()
        mediaserver.api.setup_cloud_system(cloud_account)
        system_id = mediaserver.api.get_cloud_system_id()
        system_name = f'Tile_test_system_{int(time.perf_counter_ns())}'
        cloud_account.rename_system(system_id, system_name)
        mediaserver.stop()
        additional_mediaserver = second_stand.mediaserver()
        additional_mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        additional_mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        additional_mediaserver.set_cloud_host(cloud_host)
        additional_mediaserver.start()
        additional_mediaserver.api.setup_cloud_system(cloud_account)
        browser = exit_stack.enter_context(browser_stand.browser())
        link = f"https://{cloud_host}/systems/"
        browser.open(link)
        LoginComponent(browser).login(cloud_account.user_email, cloud_account.password)
        cms_data = get_cms_settings(cloud_host)
        channel_partners_is_enabled = cms_data.flag_is_enabled('channelPartners')
        if channel_partners_is_enabled:
            systems_page = ChannelPartnerSystemTiles(browser)
        else:
            systems_page = SystemTiles(browser)
        systems_page.wait_for_systems_label()
        system_tile = systems_page.get_system_tile(system_name)
        # It takes 1 minute for the system status to be updated on Cloud portal.
        assert system_tile.has_offline_label(timeout=60)
        if not channel_partners_is_enabled:
            assert not system_tile.has_open_button()
            assert system_tile.owner_name() == "Your System"
        system_tile.click()
        system_administration_page = SystemAdministrationPage(browser)
        assert element_is_present(system_administration_page.get_offline_ribbon)
        mediaserver.start()
        browser.open(link)
        system_tile = systems_page.get_system_tile(system_name)
        # It takes 1 minute for the system status to be updated on Cloud Portal.
        system_tile.wait_until_is_online(timeout=60)
        assert not system_tile.has_offline_label(timeout=1)
        system_tile.click()
        assert _no_system_offline_ribbon(system_administration_page)


def _no_system_offline_ribbon(sys_admin_pg: SystemAdministrationPage, timeout: float = 5) -> bool:
    try:
        sys_admin_pg.get_offline_ribbon(timeout)
    except ElementNotFound:
        return True
    else:
        return False


if __name__ == '__main__':
    exit(test_check_system_state().main())
