# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from browser.chrome.provisioned_chrome import chrome_stand
from browser.color import RGBColor
from browser.css_properties import get_background_color
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from cloud_api.cloud import ensure_flags_enabled
from cloud_api.cloud import make_cloud_account_factory
from tests.base_test import CloudTest
from tests.cloud_portal._account_settings import AccountThemesComponent
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._header import AccountDropdownMenu
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._login import LoginComponent


class test_dark_theme(CloudTest):
    """Test dark theme.

    Selection-Tag: 121013
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_smoke
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/121013
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        ensure_flags_enabled(cloud_host, ['newHeader', 'themesEnabled'])
        cloud_account_factory = make_cloud_account_factory(cloud_host)
        cloud_owner = exit_stack.enter_context(cloud_account_factory.temp_account())
        services_hosts = cloud_owner.get_services_hosts()
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host, *services_hosts]))
        browser = exit_stack.enter_context(browser_stand.browser())
        link = f'https://{cloud_host}'
        browser.open(link)
        header = HeaderNav(browser)
        header.get_log_in_link().invoke()
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        _ensure_logged_in(browser)
        header.account_dropdown().invoke()
        account_dropdown = AccountDropdownMenu(browser)
        account_dropdown.account_settings_option().invoke()
        account_themes = AccountThemesComponent(browser)
        account_themes.select_dark_theme()
        assert _is_background_dark(browser, timeout=5)
        header.account_dropdown().invoke()
        account_dropdown.log_out_option().invoke()
        browser.open(link)
        # Ensure landing page is loaded.
        log_in_button = header.get_log_in_link()
        assert _is_background_dark(browser, timeout=5)
        log_in_button.invoke()
        LoginComponent(browser).login(cloud_owner.user_email, cloud_owner.password)
        _ensure_logged_in(browser)
        assert _is_background_dark(browser, timeout=5)


def _ensure_logged_in(browser: Browser) -> None:
    timeout = 5
    started_at = time.monotonic()
    while True:
        current_url = browser.get_current_url()
        if '/authorize' in current_url and 'redirect_uri' in current_url:
            raise RuntimeError(
                "User was redirected to the login page right after successful login. "
                "See: https://networkoptix.atlassian.net/browse/CLOUD-11802")
        if time.monotonic() - started_at > timeout:
            break
        time.sleep(0.5)


def _is_background_dark(browser: Browser, timeout: float) -> bool:
    selector = ByXPATH("/html/body/nx-app//div[@class='mainContainer']")
    try:
        main_container = browser.wait_element(selector, timeout=timeout)
    except ElementNotFound:
        raise RuntimeError(
            "Long page loading after login. "
            "See: https://networkoptix.atlassian.net/browse/CLOUD-14589")
    current_color = get_background_color(main_container)
    dark_grey = RGBColor(13, 14, 15)
    light_grey = RGBColor(240, 242, 244)
    if current_color.is_shade_of(dark_grey):
        return True
    elif current_color.is_shade_of(light_grey):
        return False
    else:
        raise RuntimeError(f"Unknown background color: {current_color}")


if __name__ == '__main__':
    exit(test_dark_theme().main())
