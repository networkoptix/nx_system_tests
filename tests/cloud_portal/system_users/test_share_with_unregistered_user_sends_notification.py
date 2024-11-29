# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import ElementNotFound
from cloud_api._imap import IMAPConnection
from cloud_api.cloud import get_cms_settings
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_api import Groups
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._confirmations import AccountActivatedConfirmation
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._register_form import RegisterPage
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.web_admin._interface_wait import element_is_present
from vm.networks import setup_flat_network


class test_share_with_unregistered_user_sends_notification(VMSTest, CloudTest):
    """Test share with unregistered user sends notification.

    Selection-Tag: 41889
    Selection-Tag: 30445
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_smoke
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/41889
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/30445
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        mediaserver = stand.mediaserver()
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = exit_stack.enter_context(cloud_account_factory.temp_account())
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_owner.set_user_customization(customization_name)
        cloud_owner.rename_user(f"Test_owner_{time.perf_counter_ns()}")
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
        cloud_system_id = mediaserver_api.get_cloud_system_id()
        cloud_viewer = exit_stack.enter_context(cloud_account_factory.unregistered_temp_account())
        full_name = cloud_owner.get_user_info().get_full_name()
        cloud_owner.share_system(
            cloud_system_id, cloud_viewer.user_email, user_groups=[Groups.VIEWERS])
        cms_settings = get_cms_settings(cloud_host)
        with IMAPConnection(*cloud_account_factory.get_imap_credentials()) as imap_connection:
            subject = f"{full_name} invites you to {cms_settings.get_cloud_name()}"
            message_id = imap_connection.get_message_id_by_subject(cloud_viewer.user_email, subject)
            assert imap_connection.has_link_to_cloud_instance_in_message(message_id, cloud_host)
            register_link = imap_connection.get_register_link_from_message(message_id)
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(register_link)
        register_page = RegisterPage(browser)
        email_field = register_page.get_locked_email_field()
        assert email_field.get_value() == cloud_viewer.user_email
        assert email_field.is_readonly()
        register_page.register("Mark", "Hamill", cloud_viewer.password)
        account_activated = AccountActivatedConfirmation(browser)
        account_activated.wait_for_account_activated_text()
        account_activated.log_in()
        LoginComponent(browser).login_with_password_only(cloud_viewer.password)
        assert element_is_present(HeaderNav(browser).account_dropdown)
        cms_data = get_cms_settings(cloud_host)
        if cms_data.flag_is_enabled('channelPartners'):
            # With the new Channel Partners interface, the only system doesn't open automatically.
            browser.open(f'https://{cloud_host}/systems/{cloud_system_id}')
        system_page = SystemAdministrationPage(browser)
        # It takes time for the system status to be updated on Cloud portal.
        assert _shared_system_is_opened(system_page, timeout=90)


def _shared_system_is_opened(system_page: SystemAdministrationPage, timeout: float) -> bool:
    try:
        system_page.wait_for_system_name_field(timeout=timeout)
    except ElementNotFound:
        return False
    else:
        return True


if __name__ == '__main__':
    exit(test_share_with_unregistered_user_sends_notification().main())
