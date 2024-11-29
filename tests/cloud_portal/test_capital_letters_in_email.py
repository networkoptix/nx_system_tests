# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api._imap import IMAPConnection
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
from tests.cloud_portal._confirmations import AccountCreatedConfirmation
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._register_form import RegisterPage
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from vm.networks import setup_flat_network


class test_capital_letters_in_email(VMSTest, CloudTest):
    """Test capital letters email.

    Selection-Tag: 120916
    Selection-Tag: cloud_portal
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/120916
    """

    def _run(self, args, exit_stack):
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        stand = exit_stack.enter_context(pool.one_mediaserver('ubuntu22'))
        mediaserver = stand.mediaserver()
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = cloud_account_factory.create_account()
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_owner.set_user_customization(customization_name)
        cloud_user_one = cloud_account_factory.create_account()
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
        cloud_owner.share_system(
            cloud_system_id, cloud_user_one.user_email, user_groups=[Groups.VIEWERS])
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f"https://{cloud_host}/")
        header = HeaderNav(browser)
        header.get_create_account_link().invoke()
        cloud_user_two = cloud_account_factory.create_unregistered_account()
        RegisterPage(browser).register_with_email(
            cloud_user_two.user_email.upper(),
            "Mark",
            "Hamill",
            cloud_user_two.password,
            )
        AccountCreatedConfirmation(browser).wait_for_account_created_text()
        with IMAPConnection(
                *cloud_account_factory.get_imap_credentials()) as imap_connection:
            activation_link = imap_connection.get_activation_link_from_message_within_timeout(
                cloud_user_two.user_email)
        browser.open(activation_link)
        account_activated = AccountActivatedConfirmation(browser)
        account_activated.wait_for_account_activated_text()
        cloud_owner.share_system(
            cloud_system_id, cloud_user_two.user_email.upper(), user_groups=[Groups.VIEWERS])
        link_to_system = f"https://{cloud_host}/systems/{cloud_system_id}"
        browser.open(link_to_system)
        LoginComponent(browser).login(cloud_user_one.user_email.upper(), cloud_user_one.password)
        system_administration_page = SystemAdministrationPage(browser)
        # Just after user is set up and connected to Cloud system the System Administration page
        # can be loaded with a huge delay. Ensure page is loaded by waiting for System Name field.
        system_administration_page.wait_for_system_name_field(timeout=60)
        header.account_dropdown().invoke()
        AccountDropdownMenu(browser).log_out_option().invoke()
        browser.open(link_to_system)
        LoginComponent(browser).login(cloud_user_two.user_email.lower(), cloud_user_two.password)
        # Just after user is set up and connected to Cloud system the System Administration page
        # can be loaded with a huge delay. Ensure page is loaded by waiting for System Name field.
        system_administration_page.wait_for_system_name_field(timeout=60)


if __name__ == '__main__':
    exit(test_capital_letters_in_email().main())
