# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ElementNotFound
from cloud_api.cloud import ensure_flags_enabled
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import MediaserverApi
from mediaserver_api import Permissions
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._not_existing_page import FailedToAccessSystemPage
from tests.cloud_portal._system_left_menu import UsersDropdown
from tests.cloud_portal._system_users import SystemUsers
from vm.networks import setup_flat_network


class test_owner_can_remove_user(VMSTest, CloudTest):
    """Test owner can remove user.

    Selection-Tag: 41903
    Selection-Tag: 41888
    Selection-Tag: 94719
    Selection-Tag: 30726
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_gitlab
    Selection-Tag: cloud_portal_smoke
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/41903
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/41888
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/94719
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30726
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        ensure_flags_enabled(cloud_host, ['newHeader'])
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        mediaserver = stand.mediaserver()
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = exit_stack.enter_context(cloud_account_factory.temp_account())
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_owner.set_user_customization(customization_name)
        services_hosts = cloud_owner.get_services_hosts()
        mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        mediaserver.set_cloud_host(cloud_host)
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        mediaserver.start()
        mediaserver_api = stand.api()
        mediaserver_api.setup_cloud_system(cloud_owner)
        cloud_viewer = exit_stack.enter_context(cloud_account_factory.temp_account())
        cloud_viewer.set_user_customization(customization_name)
        mediaserver_api.add_cloud_user(
            name=cloud_viewer.user_email,
            email=cloud_viewer.user_email,
            permissions=Permissions.VIEWER_PRESET,
            )
        browser = exit_stack.enter_context(browser_stand.browser())
        link = f"https://{cloud_host}/systems/{mediaserver_api.get_cloud_system_id()}"
        browser.open(link)

        assert _has_user_with_email(mediaserver_api, cloud_viewer.user_email)
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        users_dropdown = UsersDropdown(browser)
        users_dropdown.open()
        users_dropdown.get_user_with_email(cloud_viewer.user_email).invoke()
        users_page = SystemUsers(browser)
        users_page.remove_user_button().invoke()
        users_page.remove_user_modal_button().invoke()
        users_page.wait_until_remove_modal_disappears()
        header = HeaderNav(browser)
        header.account_dropdown().invoke()
        AccountDropdownMenu(browser).log_out_option().invoke()
        assert not _has_user_with_email(mediaserver_api, cloud_viewer.user_email)

        _wait_for_correct_location(browser, url=f"https://{cloud_host}/")
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_viewer.user_email, cloud_viewer.password)
        assert element_is_present(header.account_dropdown)
        browser.open(link)
        try:
            FailedToAccessSystemPage(browser).wait_for_failed_to_access_text()
        except ElementNotFound:
            raise AssertionError(
                "Redirects to home page but does not load disconnected system."
                "See: https://networkoptix.atlassian.net/browse/CLOUD-14034")


def _wait_for_correct_location(browser: Browser, url: str):
    started_at = time.monotonic()
    while True:
        if browser.get_current_url() == url:
            return
        if time.monotonic() - started_at > 10:
            raise RuntimeError(
                f"Wrong location. Expected {url}, got {browser.get_current_url()}")
        time.sleep(0.5)


def _has_user_with_email(api: MediaserverApi, email: str):
    return email in {user.email for user in api.list_users()}


if __name__ == '__main__':
    exit(test_owner_can_remove_user().main())
