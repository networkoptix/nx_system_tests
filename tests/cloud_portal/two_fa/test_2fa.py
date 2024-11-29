# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api.cloud import ensure_flags_enabled
from cloud_api.cloud import make_cloud_account_factory
from doubles.totp import TimeBasedOtp
from tests.base_test import CloudTest
from tests.cloud_portal._account_settings import AccountSecurityComponent
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._translation import en_us
from tests.cloud_portal.two_fa._2fa_modal import DisableTwoFAModal
from tests.cloud_portal.two_fa._2fa_modal import EnableTwoFAModal


class test_2fa(CloudTest):
    """Test enable and disable 2FA.

    Selection-Tag: 107768
    Selection-Tag: 107771
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_smoke
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/107768
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/107771
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        ensure_flags_enabled(cloud_host, ['newHeader'])
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = exit_stack.enter_context(cloud_account_factory.temp_account())
        services_hosts = cloud_owner.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        browser = exit_stack.enter_context(browser_stand.browser())
        # TestRail scenario 107768, enable 2FA.
        browser.open(f'https://{cloud_host}')
        header = HeaderNav(browser, en_us)
        header.get_log_in_link().invoke()
        login_component = LoginComponent(browser)
        login_component.login(cloud_owner.user_email, cloud_owner.password)
        header.account_dropdown().invoke()
        account_dropdown = AccountDropdownMenu(browser)
        account_dropdown.security_option().invoke()
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
        enable_2fa_modal.close_by_ok()
        account_security_component.wait_for_2fa_enabled_badge()
        header.account_dropdown().invoke()
        account_dropdown.log_out_option().invoke()
        browser.open(f"https://{cloud_host}/")
        header_2 = HeaderNav(browser, en_us)
        header_2.get_log_in_link().invoke()
        login_component_2 = LoginComponent(browser)
        login_component_2.login(cloud_owner.user_email, cloud_owner.password)
        login_component_2.submit_totp_code(totp.generate_otp())
        assert element_is_present(header_2.account_dropdown)
        # TestRail scenario 107771, disable 2FA.
        header_2.account_dropdown().invoke()
        account_dropdown_2 = AccountDropdownMenu(browser)
        account_dropdown_2.security_option().invoke()
        account_security_component_2 = AccountSecurityComponent(browser)
        account_security_component_2.wait_for_2fa_enabled_badge()
        account_security_component_2.get_disable_2fa_button().invoke()
        disable_2fa_modal = DisableTwoFAModal(browser)
        disable_2fa_modal.submit_totp_code(totp.generate_otp())
        account_security_component_2.wait_for_2fa_disabled_badge()
        header_2.account_dropdown().invoke()
        account_dropdown_2.log_out_option().invoke()
        browser.open(f"https://{cloud_host}/")
        header_3 = HeaderNav(browser, en_us)
        header_3.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        assert element_is_present(header_3.account_dropdown)


if __name__ == '__main__':
    exit(test_2fa().main())
