# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api._imap import IMAPConnection
from cloud_api.cloud import make_cloud_account_factory
from tests.base_test import CloudTest
from tests.cloud_portal._change_pass import SetNewPasswordForm
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._confirmations import PasswordSetConfirmation
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._login import ResetPasswordComponent
from tests.cloud_portal._translation import en_us


class test_restore_password(CloudTest):
    """Test restore password en_us.

    Selection-Tag: 94722
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_smoke
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/94722
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_user = exit_stack.enter_context(cloud_account_factory.temp_account())
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host]))
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f"https://{cloud_host}/")
        header = HeaderNav(browser)
        header.get_log_in_link().invoke()
        login_component = LoginComponent(browser)
        login_component.get_email_field().put(cloud_user.user_email)
        login_component.get_next_button().invoke()
        login_component.get_forgot_password_button().invoke()
        reset_password = ResetPasswordComponent(browser)
        assert reset_password.get_email_field().get_value() == cloud_user.user_email
        reset_password.get_reset_password_button().invoke()
        with IMAPConnection(*cloud_account_factory.get_imap_credentials()) as imap_connection:
            subject = en_us.tr('RESET_PASSWORD_EMAIL_SUBJECT')
            message_id = imap_connection.get_message_id_by_subject(
                cloud_user.user_email,
                subject,
                )
            restore_password_link = imap_connection.get_restore_password_link(message_id)
        browser.open(restore_password_link)
        set_new_password = SetNewPasswordForm(browser)
        new_password = "ArbitraryPassword"
        set_new_password.get_password_field().set_password(new_password)
        set_new_password.get_next_button().invoke()
        password_set_confirmation = PasswordSetConfirmation(browser)
        password_set_confirmation.wait_for_set_new_password_text()
        password_set_confirmation.wait_for_password_is_set_text()
        cloud_user.set_password(new_password)  # To be able to remove the user on teardown
        password_set_confirmation.open_login_page()
        LoginComponent(browser).login_with_password_only(new_password)
        assert element_is_present(header.account_dropdown)


if __name__ == '__main__':
    exit(test_restore_password().main())
