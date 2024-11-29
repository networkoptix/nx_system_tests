# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.html_elements import HyperLink
from browser.webdriver import Browser
from browser.webdriver import ByText
from browser.webdriver import ByXPATH


class NotExistingPage:

    def __init__(self, browser: Browser):
        self._browser = browser

    def wait_for_page_not_found_text(self) -> None:
        selector = ByXPATH.quoted(
            "//nx-404//h2[contains(text(), %s)]",
            "Page not found",
            )
        self._browser.wait_element(selector, 5)

    def get_go_to_main_page_link(self) -> HyperLink:
        selector = ByXPATH.quoted(
            "//nx-404//button/a[contains(text(), %s)]",
            "Go to Main Page",
            )
        return HyperLink(self._browser.wait_element(selector, 5))


class FailedToAccessSystemPage:

    def __init__(self, browser: Browser):
        self._browser = browser

    def wait_for_failed_to_access_text(self) -> None:
        self._browser.wait_element(ByText("Failed to access system"), 10)
