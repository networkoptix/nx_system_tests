# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ElementNotFound
from cloud_api._cloud import CloudAccount
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
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import DisconnectFromCloudModal
from tests.cloud_portal._system_administration_page import DisconnectedFromCloudToast
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._translation import en_us
from vm.networks import setup_flat_network

_logger = logging.getLogger(__name__)


class test_owner_can_disconnect_offline_system(VMSTest, CloudTest):
    """Test disconnect offline system from Cloud Portal.

    Selection-Tag: 41897
    Selection-Tag: cloud_portal
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/41897
    """

    def _run(self, args, exit_stack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        server_stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        cloud_owner = cloud_account_factory.create_account()
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
        system_id = mediaserver.api.get_cloud_system_id()
        system_name = f'Disconnect_offline_system_{time.perf_counter_ns()}'
        cloud_owner.rename_system(system_id, system_name)
        mediaserver.stop()
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f"https://{cloud_host}/systems/{system_id}")
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        _retry_system_offline_check(browser, cloud_owner, cloud_host)
        system_administration_page = SystemAdministrationPage(browser)
        system_administration_page.get_disconnect_from_cloud_button().invoke()
        disconnect_account_modal = DisconnectFromCloudModal(browser)
        disconnect_account_modal.get_disconnect_system_button().invoke()
        cms_settings = get_cms_settings(cloud_host)
        cloud_name = cms_settings.get_cloud_name()
        disconnected_toast = DisconnectedFromCloudToast(browser, en_us, cloud_name=cloud_name)
        disconnected_toast.wait_until_shown(timeout=2)
        disconnected_toast.wait_until_not_shown(timeout=10)
        _wait_for_url(browser, url=f"https://{cloud_host}/systems")
        assert element_is_present(system_administration_page.get_no_systems_text)


def _retry_system_offline_check(
        browser: Browser,
        owner: CloudAccount,
        cloud_host: str,
        max_attempts: int = 3,
        ):
    attempt = 1
    while True:
        try:
            SystemAdministrationPage(browser).get_offline_ribbon()
            break
        except ElementNotFound:
            if attempt > max_attempts:
                raise
            attempt += 1
            # Sometimes the system offline ribbon does not show up after the first attempt.
            # See: https://networkoptix.atlassian.net/browse/CLOUD-14340
            _logger.debug(
                "%s system offline assertion(s) failed due to CLOUD-14340, retrying",
                attempt)
            HeaderNav(browser).account_dropdown().invoke()
            AccountDropdownMenu(browser).log_out_option().invoke()
            browser.open(f"https://{cloud_host}")
            HeaderNav(browser).get_log_in_link().invoke()
            LoginComponent(browser).login(owner.user_email, owner.password)


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
    exit(test_owner_can_disconnect_offline_system().main())
