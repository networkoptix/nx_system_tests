# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from ipaddress import IPv4Network

from browser.chrome.provisioned_chrome import chrome_stand
from browser.color import RGBColor
from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import CursorStyle
from browser.webdriver import Keys
from browser.webdriver import VisibleElement
from cloud_api.cloud import ensure_flags_enabled
from cloud_api.cloud import get_cms_settings
from cloud_api.cloud import make_cloud_account_factory
from directories import get_run_dir
from installation import ClassicInstallerSupplier
from installation import public_ip_check_addresses
from mediaserver_scenarios.provisioned_mediaservers import FTMachinePool
from tests.base_test import CloudTest
from tests.base_test import VMSTest
from tests.cloud_portal._account_settings import AccountInformation
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent
from tests.cloud_portal._system_administration_page import SystemAdministrationPage
from tests.cloud_portal._system_left_menu import UsersDropdown
from tests.cloud_portal._system_tiles import ChannelPartnerSystemTiles
from tests.cloud_portal._system_tiles import SystemTiles
from tests.cloud_portal._system_users import SystemUsers
from tests.cloud_portal._toast_notification import SuccessToast
from tests.cloud_portal._translation import en_us
from vm.networks import setup_flat_network

_logger = logging.getLogger(__name__)

ERROR_COLOR = RGBColor(240, 44, 44)


class test_user_can_change_name(VMSTest, CloudTest):
    """Test user can change his name and a valid name is saved on the user's system page.

    Selection-Tag: 41573
    Selection-Tag: cloud_portal
    Testrail: https://networkoptix.testrail.net/index.php?/cases/view/41573
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
        cloud_owner = cloud_account_factory.create_account()
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
        system_id = mediaserver.api.get_cloud_system_id()
        system_name = f'User_can_change_name_{time.perf_counter_ns()}'
        cloud_owner.rename_system(system_id, system_name)
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f"https://{cloud_host}")
        header = HeaderNav(browser)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        cms_data = get_cms_settings(cloud_host)
        channel_partners_is_enabled = cms_data.flag_is_enabled('channelPartners')
        if channel_partners_is_enabled:
            systems_page = ChannelPartnerSystemTiles(browser)
        else:
            systems_page = SystemTiles(browser)
        systems_page.wait_for_systems_label()
        systems_page.get_system_tile(system_name).click()
        SystemAdministrationPage(browser).wait_for_system_name_field(timeout=90)
        header.account_dropdown().invoke()
        AccountDropdownMenu(browser).account_settings_option().invoke()
        account_information = AccountInformation(browser)
        first_name_field = account_information.first_name_field()
        last_name_field = account_information.last_name_field()
        first_name_field.clear()
        first_name_field.put("x")
        first_name_field.invoke()
        browser.request_keyboard().send_keys(Keys.BACKSPACE)
        last_name_field.invoke()
        save_button = account_information.save_button()
        cancel_button = account_information.cancel_button()
        _wait_for_red_border(first_name_field)
        _wait_for_red_text(first_name_field)
        assert cancel_button.is_active()
        assert not save_button.is_active()
        assert not _cursor_is_allowed(save_button)
        first_name_field.put("   ")
        last_name_field.invoke()
        _wait_for_red_border(first_name_field)
        _wait_for_red_text(first_name_field)
        assert cancel_button.is_active()
        assert not save_button.is_active()
        assert not _cursor_is_allowed(save_button)
        first_name_field.clear()
        first_name_field.put("Valid")
        last_name_field.clear()
        last_name_field.put("x")
        last_name_field.invoke()
        browser.request_keyboard().send_keys(Keys.BACKSPACE)
        first_name_field.invoke()
        _wait_for_red_border(last_name_field)
        _wait_for_red_text(last_name_field)
        assert cancel_button.is_active()
        assert not save_button.is_active()
        assert not _cursor_is_allowed(save_button)
        last_name_field.put("   ")
        first_name_field.invoke()
        _wait_for_red_border(last_name_field)
        _wait_for_red_text(last_name_field)
        assert cancel_button.is_active()
        assert not save_button.is_active()
        assert not _cursor_is_allowed(save_button)
        last_name_field.clear()
        last_name_field.put("Valid")
        first_name_field.invoke()
        assert cancel_button.is_active()
        assert save_button.is_active()
        assert _cursor_is_allowed(save_button)
        last_name_border_color = last_name_field.get_border_style()
        last_name_text_color = last_name_field.get_text_color()
        assert not last_name_border_color.is_encircled_by(ERROR_COLOR), (
            f"Expected border color {ERROR_COLOR}, got {last_name_border_color}")
        assert not last_name_text_color.is_shade_of(ERROR_COLOR), (
            f"Expected text color {ERROR_COLOR}, got {last_name_text_color}")
        first_name_border_color = first_name_field.get_border_style()
        first_name_text_color = first_name_field.get_text_color()
        assert not first_name_border_color.is_encircled_by(ERROR_COLOR), (
            f"Expected border color {ERROR_COLOR}, got {first_name_border_color}")
        assert not first_name_text_color.is_shade_of(ERROR_COLOR), (
            f"Expected text color {ERROR_COLOR}, got {first_name_text_color}")
        save_button.invoke()
        assert SuccessToast(browser).get_text() == en_us.tr("ACCOUNT_SAVED")
        assert "Valid" == first_name_field.get_value()
        assert "Valid" == last_name_field.get_value()
        browser.open(f'https://{cloud_host}/systems/{system_id}')
        SystemAdministrationPage(browser).wait_for_page_to_be_ready(timeout=90)
        users_dropdown = UsersDropdown(browser)
        users_dropdown.open()
        users_dropdown.get_user_with_email(cloud_owner.user_email).invoke()
        system_user = SystemUsers(browser)
        assert cloud_owner.user_email in system_user.get_user_header_text()
        _wait_for_user_name(browser, "Valid Valid")


def _wait_for_red_border(input: InputField) -> None:
    started_at = time.monotonic()
    while True:
        current_color = input.get_border_style()
        if current_color.is_encircled_by(ERROR_COLOR):
            return
        if time.monotonic() - started_at > 2:
            raise RuntimeError(f"Border error color is {current_color} instead of {ERROR_COLOR}")
        time.sleep(0.1)


def _wait_for_red_text(input: InputField) -> None:
    started_at = time.monotonic()
    while True:
        current_color = input.get_text_color()
        if current_color.is_shade_of(ERROR_COLOR):
            return
        if time.monotonic() - started_at > 2:
            raise RuntimeError(f"Text error color is {current_color} instead of {ERROR_COLOR}")
        time.sleep(0.1)


def _cursor_is_allowed(element: VisibleElement) -> bool:
    started_at = time.monotonic()
    while True:
        cursor_style = element.get_cursor_style()
        if cursor_style == CursorStyle.NOT_ALLOWED:
            return False
        if time.monotonic() - started_at > 2:
            return True
        time.sleep(0.1)


def _wait_for_user_name(browser: Browser, expected_name: str) -> None:
    timeout = 30
    started_at = time.monotonic()
    while True:
        actual_user_name = SystemUsers(browser).get_username_text()
        if expected_name in actual_user_name:
            return
        if time.monotonic() - started_at > timeout:
            raise RuntimeError(
                f"Timed out waiting for user {expected_name}. "
                f"Current {actual_user_name}. "
                f"Can be caused by https://networkoptix.atlassian.net/browse/CLOUD-14485")
        _logger.info(
            f"Waiting for user {expected_name} name to appear, current {actual_user_name}")
        browser.refresh()
        time.sleep(2)


if __name__ == '__main__':
    exit(test_user_can_change_name().main())
