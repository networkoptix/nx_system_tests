# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from browser.webdriver import AttributeNotFound
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementSelector


class NxSwitch:

    def __init__(self, browser: Browser, selector: ElementSelector):
        self._browser = browser
        self._element = self._browser.wait_element(selector, 5)

    def is_switched_on(self) -> bool:
        status_element = ByXPATH(".//input").find_in(self._element)
        try:
            return "selected" in status_element.get_attribute("class")
        except AttributeNotFound:
            return False

    def turn_on(self) -> None:
        if self.is_switched_on():
            _logger.debug("Switch is already on")
        else:
            self._element.invoke()

    def turn_off(self) -> None:
        if not self.is_switched_on():
            _logger.debug("Switch is already off")
        else:
            self._element.invoke()


_logger = logging.getLogger(__name__)
