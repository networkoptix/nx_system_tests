# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from browser.chrome.provisioned_chrome import chrome_stand
from browser.html_elements import HyperLink
from browser.webdriver import Browser
from browser.webdriver import ElementNotInteractable
from tests.base_test import CloudTest
from tests.cloud_portal._collect_version import collect_version
from tests.cloud_portal._not_existing_page import NotExistingPage


class test_misc(CloudTest):
    """Open nonexistent page for 404.

    Selection-Tag: 41565
    Selection-Tag: cloud_portal
    Selection-Tag: cloud_portal_gitlab
    Selection-Tag: cloud_portal_smoke
    TestRail: https://networkoptix.testrail.net/index.php?/cases/view/41565
    """

    def _run(self, args, exit_stack):
        cloud_host = args.cloud_host
        collect_version(cloud_host)
        browser_stand = exit_stack.enter_context(chrome_stand([cloud_host]))
        browser = exit_stack.enter_context(browser_stand.browser())
        browser.open(f"https://{cloud_host}/not_existing")
        not_existing_page = NotExistingPage(browser)
        not_existing_page.wait_for_page_not_found_text()
        go_to_main_page_link = not_existing_page.get_go_to_main_page_link()
        _invoke_when_interactable(go_to_main_page_link)
        _wait_for_url(browser, f"https://{cloud_host}/")


def _invoke_when_interactable(link: HyperLink) -> None:
    timeout = 5
    started_at = time.monotonic()
    while True:
        try:
            link.invoke()
        except ElementNotInteractable:
            if time.monotonic() - started_at > timeout:
                raise
            _logger.debug(
                "Link %r is not interactable. Trying to invoke again after a delay", link)
            time.sleep(0.5)
        else:
            break


def _wait_for_url(browser: Browser, expected_url: str):
    timeout_sec = 5
    started_at = time.monotonic()
    while True:
        current_url = browser.get_current_url()
        if current_url == expected_url:
            return
        if time.monotonic() - started_at > timeout_sec:
            raise RuntimeError(
                f"Wrong email after {timeout_sec} seconds. "
                f"Expected {expected_url} got {current_url}")
        time.sleep(0.5)


_logger = logging.getLogger(__name__)

if __name__ == '__main__':
    exit(test_misc().main())
