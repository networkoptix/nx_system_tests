# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import os
import platform
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from cloud_api.cloud import get_cms_settings
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from doubles.totp import TimeBasedOtp
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._account_settings import AccountSecurityComponent
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._element_wait import element_is_present
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._system_tiles import ChannelPartnerSystemTiles
from tests.cloud_portal._system_tiles import SystemTiles
from tests.cloud_portal._toast_notification import SuccessToast
from tests.cloud_portal._translation import en_us
from tests.cloud_portal.two_fa._2fa_modal import EnableTwoFAModal
from tests.cloud_portal.two_fa._2fa_modal import RequireCode2FAModal
from tests.cloud_portal.two_fa._2fa_modal import ToggleSystem2FAModal
from vm.networks import setup_flat_network


class test_system_2fa(VMSTest, CloudTest):
    """Test mandatory 2FA for specific systems.

    Selection-Tag: C110067
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_smoke
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/110067
    """

    def _run(self, args, exit_stack):
        one_vm_type = 'ubuntu22'
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        installer_supplier = ClassicInstallerSupplier(args.distrib_url)
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        pool = FTMachinePool(installer_supplier, get_run_dir(), 'v2')
        first_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
        second_stand = exit_stack.enter_context(pool.one_mediaserver(one_vm_type))
        cloud_owner = exit_stack.enter_context(cloud_account_factory.temp_account())
        customization_name = installer_supplier.distrib().customization().customization_name
        cloud_owner.set_user_customization(customization_name)
        services_hosts = cloud_owner.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        setup_flat_network(
            [first_stand.vm(), second_stand.vm(), browser_stand.vm()],
            IPv4Network('10.254.10.0/28'),
            )
        unique_run_id = f"{platform.node()}_{os.getpid()}_{time.time_ns()}"
        first_mediaserver = first_stand.mediaserver()
        first_mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        first_mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        first_mediaserver.set_cloud_host(cloud_host)
        first_mediaserver.start()
        first_mediaserver.api.setup_cloud_system(cloud_owner)
        first_system_id = first_mediaserver.api.get_cloud_system_id()
        first_system_name = f'Tile_first_system_{unique_run_id}'
        cloud_owner.rename_system(first_system_id, first_system_name)
        second_mediaserver = second_stand.mediaserver()
        second_mediaserver.os_access.cache_dns_in_etc_hosts([cloud_host, *services_hosts, *public_ip_check_addresses])
        second_mediaserver.allow_access_to_cloud(cloud_host, services_hosts=services_hosts)
        second_mediaserver.set_cloud_host(cloud_host)
        second_mediaserver.start()
        second_mediaserver.api.setup_cloud_system(cloud_owner)
        second_system_id = second_mediaserver.api.get_cloud_system_id()
        second_system_name = f'Tile_second_system_{unique_run_id}'
        cloud_owner.rename_system(second_system_id, second_system_name)
        services_hosts = cloud_owner.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f'https://{cloud_host}')
        header = HeaderNav(browser, en_us)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        header.account_dropdown().invoke()
        account_dropdown = AccountDropdownMenu(browser)
        # Enable 2FA but don't require on basic logins.
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
        assert account_security_component.twofa_is_required_on_every_login()
        account_security_component.turn_off_2fa_requirement_on_login()
        RequireCode2FAModal(browser).submit_totp_code(totp.generate_otp())
        browser.open(f'https://{cloud_host}/systems')
        cms_data = get_cms_settings(cloud_host)
        if cms_data.flag_is_enabled('channelPartners'):
            system_tiles = ChannelPartnerSystemTiles(browser)
        else:
            system_tiles = SystemTiles(browser)
        assert system_tiles.has_system_tile(first_system_name)
        assert system_tiles.has_system_tile(second_system_name)
        # Enable mandatory 2FA on system 1.
        system_tiles.get_system_tile(first_system_name).click()
        system_admin = SystemAdministrationPage(browser)
        system_admin.wait_for_system_name_field(timeout=90)
        system_admin.turn_on_mandatory_2fa()
        ToggleSystem2FAModal(browser).submit_totp_code(totp.generate_otp())
        assert en_us.tr('SYSTEM_2FA_ENABLED') in SuccessToast(browser).get_text()
        header.account_dropdown().invoke()
        account_dropdown.log_out_option().invoke()
        browser.open(f"https://{cloud_host}/")
        # Login and verify 2FA is required only when accessing system 1.
        header_2 = HeaderNav(browser)
        header_2.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        assert element_is_present(header_2.account_dropdown)
        locked_system = system_tiles.get_system_tile(first_system_name)
        assert element_is_present(locked_system.get_lock_icon)
        unlocked_system = system_tiles.get_system_tile(second_system_name)
        assert not element_is_present(unlocked_system.get_lock_icon)
        locked_system.click()
        LoginComponent(browser).submit_totp_code(totp.generate_otp())
        SystemAdministrationPage(browser).wait_for_system_name_field(timeout=30)
        header_2.account_dropdown().invoke()
        AccountDropdownMenu(browser).log_out_option().invoke()
        # Login to system 2 and verify no 2FA is required.
        browser.open(f"https://{cloud_host}/systems/{second_system_id}")
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        SystemAdministrationPage(browser).wait_for_system_name_field(timeout=30)
        HeaderNav(browser, en_us).account_dropdown().invoke()
        AccountDropdownMenu(browser).log_out_option().invoke()
        # Login to system 1 and verify 2FA is required.
        browser.open(f"https://{cloud_host}/systems/{first_system_id}")
        login_component_2 = LoginComponent(browser)
        login_component_2.login(cloud_owner.user_email, cloud_owner.password)
        login_component_2.submit_totp_code(totp.generate_otp())
        system_admin_2 = SystemAdministrationPage(browser)
        system_admin_2.wait_for_system_name_field(timeout=90)
        system_admin_2.turn_off_mandatory_2fa()
        ToggleSystem2FAModal(browser).submit_totp_code(totp.generate_otp())


if __name__ == '__main__':
    exit(test_system_2fa().main())
