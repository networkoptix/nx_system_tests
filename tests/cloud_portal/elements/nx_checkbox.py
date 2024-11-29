# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementSelector


class NxCheckbox:

    def __init__(self, browser: Browser, selector: ElementSelector):
        self._browser = browser
        self._element = self._browser.wait_element(selector, 5)

    def is_checked(self) -> bool:
        status_element = ByXPATH(".//span[1]").find_in(self._element)
        checked_status = status_element.get_attribute("class")
        if checked_status == "tick checked":
            return True
        elif checked_status == "tick unchecked":
            return False
        else:
            raise RuntimeError(f"NxCheckbox class unrecognized: {checked_status}")

    def check(self) -> None:
        if self.is_checked():
            _logger.debug("Checkbox is already checked")
        else:
            self._element.invoke()

    def uncheck(self) -> None:
        if not self.is_checked():
            _logger.debug("Checkbox is already unchecked")
        else:
            self._element.invoke()


_logger = logging.getLogger(__name__)
