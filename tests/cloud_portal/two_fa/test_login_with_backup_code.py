# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api import CloudAccount
from cloud_api.cloud import make_cloud_account_factory
from doubles.totp import TimeBasedOtp
from tests.base_test import CloudTest
from tests.cloud_portal._account_settings import AccountSecurityComponent
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal.two_fa._2fa_modal import EnableTwoFAModal


class test_login_with_backup_code(CloudTest):
    """
    Test 2FA login with random backup code.

    Selection-Tag: 107770
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_smoke
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/107770
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner: CloudAccount = exit_stack.enter_context(cloud_account_factory.temp_account())
        services_hosts = cloud_owner.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f'https://{cloud_host}')
        header = HeaderNav(browser)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        header.account_dropdown().invoke()
        # Turn on 2FA.
        AccountDropdownMenu(browser).security_option().invoke()
        account_security_component = AccountSecurityComponent(browser)
        account_security_component.wait_for_2fa_disabled_badge()
        account_security_component.get_enable_2fa_button().invoke()
        enable_2fa_modal = EnableTwoFAModal(browser)
        enable_2fa_modal.submit_password(cloud_owner.password)
        assert element_is_present(enable_2fa_modal.get_qr_code)
        enable_2fa_modal.get_switch_key_mode_button().invoke()
        totp = TimeBasedOtp(enable_2fa_modal.get_twofa_key())
        enable_2fa_modal.move_to_next_step()
        enable_2fa_modal.submit_totp_code(totp.generate_otp())
        backup_codes = enable_2fa_modal.get_backup_codes()
        assert len(backup_codes) == 8
        enable_2fa_modal.close_by_ok()
        cloud_owner.set_totp_generator(totp)  # To be able to remove the user on teardown
        account_security_component.wait_for_2fa_enabled_badge()
        HeaderNav(browser).account_dropdown().invoke()
        AccountDropdownMenu(browser).log_out_option().invoke()
        browser.open(f'https://{cloud_host}')
        login_component2 = LoginComponent(browser)
        header_2 = HeaderNav(browser)
        header_2.get_log_in_link().invoke()
        # Confirm test fails with bogus backup code.
        login_component2.login(cloud_owner.user_email, cloud_owner.password)
        login_component2.get_backup_code_button().invoke()
        login_component2.submit_backup_code('fake42069')
        assert element_is_present(
            login_component2.get_wrong_backup_code_error,
            ), "Log in with bogus backup code did not fail"
        # Confirm login with correct backup code.
        [first_backup_code, *_] = backup_codes
        login_component2.submit_backup_code(first_backup_code)
        assert _user_is_logged_in(HeaderNav(browser)), "Log in with good backup code failed"


def _user_is_logged_in(page: HeaderNav) -> bool:
    return element_is_present(page.account_dropdown)


if __name__ == '__main__':
    exit(test_login_with_backup_code().main())
