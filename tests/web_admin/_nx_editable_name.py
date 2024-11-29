# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import ElementSelector
from browser.webdriver import Keyboard
from browser.webdriver import Keys
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text


class EditableName:

    def __init__(self, browser: Browser, selector: ElementSelector):
        self._browser = browser
        self._selector = selector

    def is_writable(self) -> bool:
        element = self._get_element()
        try:
            ByXPATH(".//img[@src='/static/images/icons/edit.png']").find_in(element)
        except ElementNotFound:
            return False
        return True

    def get_current_value(self) -> str:
        return get_visible_text(self._get_element())

    def set(self, value: str):
        self._get_element().invoke()
        keyboard = self._browser.request_keyboard()
        _clean_nx_editable_element(keyboard)
        keyboard.send_keys(value)

    def _get_element(self) -> WebDriverElement:
        return self._browser.wait_element(self._selector, 10)


def _clean_nx_editable_element(keyboard: Keyboard):
    # nx-text-editable does not support cleaning via any methods. It seems to be driven solely
    # by keyboard and mouse events. Additionally, it re-draws itself at any action.
    keyboard.send_keys("A", modifiers=Keys.CONTROL)
    keyboard.send_keys(Keys.DELETE)
