# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api._imap import IMAPConnection
from cloud_api.cloud import make_cloud_account_factory
from tests.base_test import CloudTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._confirmations import AccountActivatedConfirmation
from tests.cloud_portal._confirmations import AccountCreatedConfirmation
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._register_form import RegisterPage


class test_create_account(CloudTest):
    """Test create account.

    Selection-Tag: 94718
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_smoke
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/94718
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = exit_stack.enter_context(cloud_account_factory.temp_account())
        services_hosts = cloud_owner.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f"https://{cloud_host}/")
        header = HeaderNav(browser)
        header.get_create_account_link().invoke()
        unregistered_user = exit_stack.enter_context(
            cloud_account_factory.unregistered_temp_account())
        RegisterPage(browser).register_with_email(
            unregistered_user.user_email,
            "Mark",
            "Hamill",
            unregistered_user.password,
            )
        AccountCreatedConfirmation(browser).wait_for_account_created_text()
        with IMAPConnection(*cloud_account_factory.get_imap_credentials()) as imap_connection:
            activation_link = imap_connection.get_activation_link_from_message_within_timeout(
                unregistered_user.user_email)
        browser.open(activation_link)
        account_activated = AccountActivatedConfirmation(browser)
        account_activated.wait_for_account_activated_text()
        account_activated.log_in()
        LoginComponent(browser).login_with_password_only(unregistered_user.password)
        assert element_is_present(header.account_dropdown)


if __name__ == '__main__':
    exit(test_create_account().main())
