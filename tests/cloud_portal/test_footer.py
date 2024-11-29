# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from contextlib import contextmanager

from browser.chrome.provisioned_chrome import chrome_stand
from browser.webdriver import Browser
from browser.webdriver import ElementNotFound
from browser.webdriver import PageNotLoaded
from cloud_api.cloud import get_cms_settings
from tests.base_test import CloudTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._eula import EULA
from tests.cloud_portal._footer import Footer
from tests.cloud_portal._header import HeaderNav
from tests.cloud_portal._translation import en_us


class test_footer(CloudTest):
    """Test footer.

    Selection-Tag: 128465
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_gitlab
    Selection-Tag: cloud_portal_smoke
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/128465
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        cms_data = get_cms_settings(cloud_host)
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host]))
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f"https://{cloud_host}/")
        footer = Footer(browser)
        _wait_for_main_page_loaded(browser)
        # Calling the link introduces an external dependency, making the test less stable.
        # Parallel test runs could also DDoS the external resource, so the call is avoided.
        copyright_link = footer.get_copyright_link()
        assert copyright_link.get_text() == f"© {cms_data.get_company_name()}"
        expected_copyright_url = cms_data.get_company_link()
        actual_copyright_url = copyright_link.get_full_url()
        assert expected_copyright_url in actual_copyright_url, (
            f"{expected_copyright_url} not in {actual_copyright_url}",
            )
        footer.get_link_by_text(en_us.tr("DOWNLOADS")).invoke()
        _wait_for_url_contains(browser, f"{cloud_host}/download", "linux")
        # Calling the link introduces an external dependency, making the test less stable.
        # Parallel test runs could also DDoS the external resource, so the call is avoided.
        system_calculator_link = footer.get_link_by_text(en_us.tr('SYSTEM_CALCULATOR'))
        expected_system_calculator_url = 'nx.networkoptix.com/calculator'
        actual_system_calculator_url = system_calculator_link.get_full_url()
        assert expected_system_calculator_url in actual_system_calculator_url, (
            f'{expected_system_calculator_url} not in {actual_system_calculator_url}',
            )
        footer.get_link_by_text(en_us.tr("TERMS")).invoke()
        _wait_for_url_contains(browser, f"{cloud_host}/content/eula")
        eula = EULA(browser)
        eula.wait_for_terms_and_conditions_text()
        footer.get_link_by_text(en_us.tr('PRIVACY')).invoke()
        expected_privacy_url = cms_data.get_privacy_link()
        with _loaded_new_tab(browser):
            _wait_for_url_contains(browser, expected_privacy_url)
        footer.get_link_by_text(en_us.tr('SUPPORT')).invoke()
        expected_support_url = cms_data.get_support_link()
        with _loaded_new_tab(browser):
            _wait_for_url_contains(browser, expected_support_url)


def _wait_for_main_page_loaded(browser: Browser):
    header = HeaderNav(browser)
    timeout = 20
    started_at = time.monotonic()
    while True:
        try:
            if header.get_log_in_link().is_active():
                return
        except ElementNotFound:
            pass
        if time.monotonic() - started_at > timeout:
            raise RuntimeError(f"Main page is not loaded after {timeout} seconds")
        time.sleep(0.5)


def _wait_for_url_contains(browser: Browser, *expected_parts: str):
    timeout_sec = 5
    started_at = time.monotonic()
    while True:
        current_url = browser.get_current_url()
        if all([part in current_url for part in expected_parts]):
            return
        if time.monotonic() - started_at > timeout_sec:
            raise RuntimeError(
                f"Wrong URL after {timeout_sec} seconds. "
                f"Expected {expected_parts} in URL, got {current_url}")
        time.sleep(0.5)


@contextmanager
def _loaded_new_tab(browser: Browser):
    [main_tab, new_tab] = browser.get_tabs()
    new_tab.switch_to()
    timeout = 5
    started_at = time.monotonic()
    while True:
        try:
            browser.get_current_url()
        except PageNotLoaded:
            if time.monotonic() - started_at > timeout:
                raise RuntimeError(f"New tab is not loaded after {timeout} seconds")
            time.sleep(0.5)
        else:
            break
    yield
    new_tab.close()
    main_tab.switch_to()  # Switching doesn't happen automatically on closing tab


if __name__ == '__main__':
    exit(test_footer().main())
