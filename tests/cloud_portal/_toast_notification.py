# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from browser.html_elements import Button
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text


class SuccessToast:

    def __init__(self, browser: Browser):
        self._browser = browser

    def _get_notification_within_timeout(self, timeout_sec: float = 5) -> WebDriverElement:
        selector = ByXPATH('//nx-app-toasts//div[@class="alert alert-success toast"]')
        return self._browser.wait_element(selector, timeout_sec)

    def get_text(self) -> str:
        return get_visible_text(self._get_notification_within_timeout())

    def wait_until_not_visible(self, timeout: float = 7) -> None:
        start = time.monotonic()
        while True:
            try:
                self._get_notification_within_timeout()
            except ElementNotFound:
                return
            if time.monotonic() - start > timeout:
                raise TimeoutError(f"Notification still visible after {timeout} seconds.")
            time.sleep(.5)


class CookieBanner:

    def __init__(self, browser: Browser):
        self._browser = browser

    def close(self):
        locator = '//nx-cookie-banner//svg-icon[contains(@data-src, "close.svg")]'
        Button(self._browser.wait_element(ByXPATH(locator), 10)).invoke()

    def is_visible(self) -> bool:
        selector = ByXPATH('//nx-cookie-banner')
        try:
            banner = self._browser.wait_element(selector, 5)
        except ElementNotFound:
            return False
        else:
            # For both cases when Cookie banner is visible or not its 'visibility' property is set
            # to 'visible'. However, the actual visibility state is regulated by the height
            # parameter to be set to 0 if the developers want to hide the banner.
            return int(banner.get_css_value("height").replace('px', '')) > 0
