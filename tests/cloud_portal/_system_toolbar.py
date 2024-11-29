# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.webdriver import Browser
from browser.webdriver import ByXPATH


class SystemToolBar:

    def __init__(self, browser: Browser):
        self._browser = browser

    def open_bookmarks(self) -> None:
        selector = ByXPATH('//nx-header//a[contains(@href, "bookmarks")]')
        self._browser.wait_element(selector, 20).invoke()

    def open_view(self) -> None:
        selector = ByXPATH('//nx-header//a[contains(@href, "view")]')
        # If more than 5 Cloud Portal tests are run simultaneously, Cloud Portal
        # becomes quite slow, and horizontal menu loads for more than 20 seconds. Reduce timeout
        # when Cloud Portal test instances become faster.
        self._browser.wait_element(selector, 30).invoke()
