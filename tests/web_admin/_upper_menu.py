# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from browser.html_elements import Button
from browser.html_elements import HyperLink
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementSelector
from browser.webdriver import StaleElementReference
from browser.webdriver import WebDriverElement


class UpperMenu:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_view_link(self) -> HyperLink:
        selector = ByXPATH("//nx-app//nx-header/header//a[text() = 'View']")
        return HyperLink(self._find_relevant(selector, 10))

    def get_settings_link(self) -> HyperLink:
        selector = ByXPATH("//nx-app//nx-header/header//a[text() = 'Settings']")
        return HyperLink(self._find_relevant(selector, 10))

    def get_information_link(self) -> HyperLink:
        selector = ByXPATH("//nx-app//nx-header/header//a[text() = 'Information']")
        return HyperLink(self._find_relevant(selector, 10))

    def get_monitoring_link(self) -> HyperLink:
        selector = ByXPATH("//nx-app//nx-header/header//a[text() = 'Monitoring']")
        return HyperLink(self._find_relevant(selector, 10))

    def get_account_settings(self) -> WebDriverElement:
        selector = ByXPATH("//nx-app//nx-header/header//button[@id='accountSettingsSelect']")
        return self._find_relevant(selector, 10)

    def _find_relevant(self, selector: ElementSelector, timeout: float) -> WebDriverElement:
        # In rare cases, just after the page load starts, some hyperlinks may be re-created
        # for unknown reasons.
        started_at = time.monotonic()
        result_element = self._browser.wait_element(selector, timeout)
        while True:
            time.sleep(0.3)
            try:
                result_element.http_get("/name")
            except StaleElementReference:
                now = time.monotonic()
                if now - started_at > timeout:
                    raise
                time_spent = now - started_at
                result_element = self._browser.wait_element(selector, timeout - time_spent)
                continue
            return result_element


class AccountSettingsMenu:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_log_out_button(self) -> Button:
        xpath = "//header//div[@aria-labelledby='accountSettingsSelect']//a[contains(., 'Log Out')]"
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))
