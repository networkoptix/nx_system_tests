# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
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
from vm.networks import setup_flat_network


class test_connect_system_to_cloud_via_api(VMSTest, CloudTest):
    """Test connect system to Cloud via API.

    Selection-Tag: 30826
    Selection-Tag: cloud_portal
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/30826
    """

    def _run(self, args, exit_stack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        server_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        cloud_account = cloud_account_factory.create_account()
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_account.set_user_customization(customization_name)
        services_hosts = cloud_account.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [server_stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver = server_stand.mediaserver()
        mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        mediaserver.start()
        mediaserver.api.setup_cloud_system(cloud_account)
        system_id = mediaserver.api.get_cloud_system_id()
        system_name = f'Tile_test_system_{int(time.perf_counter_ns())}'
        cloud_account.rename_system(system_id, system_name)
        browser = exit_stack.enter_context(browser_stand.browser())
        cms_data = get_cms_settings(cloud_host)
        if cms_data.flag_is_enabled('channelPartners'):
            # With the new Channel Partners interface, the only system doesn't open automatically.
            browser.open(f'https://{cloud_host}/systems/{system_id}')
        else:
            browser.open(f'https://{cloud_host}/systems/')
        LoginComponent(browser).login(cloud_account.user_email, cloud_account.password)
        # It takes time for the system status to be updated on Cloud portal.
        system_administration_page = SystemAdministrationPage(browser)
        system_administration_page.wait_for_system_name_field(timeout=90)
        _wait_for_owner_text(
            system_administration_page,
            text="Owner – you(change)",
            timeout=20,
            )
        assert element_is_present(system_administration_page.get_change_system_name_button)
        assert element_is_present(system_administration_page.get_merge_with_another_system_button)
        assert element_is_present(system_administration_page.get_disconnect_from_cloud_button)


def _wait_for_owner_text(system_administration: SystemAdministrationPage, text: str, timeout: float):
    start_time = time.monotonic()
    end_time = start_time + timeout
    while True:
        if system_administration.get_owner_text() == text:
            break
        if time.monotonic() > end_time:
            raise RuntimeError(f"Owner text is not updated in {timeout} seconds")
        time.sleep(0.3)


if __name__ == '__main__':
    exit(test_connect_system_to_cloud_via_api().main())
