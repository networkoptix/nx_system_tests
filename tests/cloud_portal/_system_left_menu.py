# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from browser.html_elements import Button
from browser.html_elements import HyperLink
from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import ByCSS
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import Keys
from browser.webdriver import StaleElementReference
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text

_logger = logging.getLogger(__name__)


class SystemLeftMenu:

    def __init__(self, browser: Browser):
        self._browser = browser

    def wait_until_visible(self) -> None:
        try:
            self._browser.wait_element(ByXPATH.quoted("//div[@class=%s]", "nx-menu"), 15)
        except ElementNotFound:
            raise RuntimeError("Current page does not contain NX Main Menu")

    def open_servers(self) -> None:
        servers_link = HyperLink(self._browser.wait_element(ByCSS("#servers"), 5))
        servers_link.invoke()

    def wait_for_server_with_name(self, server_name) -> None:
        xpath = ByXPATH.quoted(
            "//nx-system-settings-component//nx-menu//nx-search-highlight[contains(text(), %s)]",
            server_name,
            )
        self._browser.wait_element(xpath, 5)

    def open_cameras(self) -> None:
        servers_link = HyperLink(self._browser.wait_element(ByCSS("#cameras"), 5))
        servers_link.invoke()

    def wait_for_camera_with_name(self, camera_name: str) -> None:
        xpath = ByXPATH.quoted(
            "//nx-system-settings-component//nx-menu//nx-search-highlight[contains(text(), %s)]",
            camera_name,
            )
        self._browser.wait_element(xpath, 5)


class UsersDropdown:

    def __init__(self, browser: Browser):
        self._browser = browser

    def open(self) -> None:
        if self._is_open():
            return
        # Sometimes element is in the process of changing its state while we try to find it.
        # To avoid such instability try to find it one more time with a small delay.
        try:
            self._get_users_dropdown_button().invoke()
        except StaleElementReference:
            _logger.info(
                "Users dropdown button is not loaded completely. Clicking with a little delay")
            time.sleep(0.5)
            self._get_users_dropdown_button().invoke()
        self.add_user_button()

    def _is_open(self) -> bool:
        try:
            self.add_user_button(timeout_sec=5)
        except ElementNotFound:
            return False
        return True

    def _get_users_dropdown_button(self) -> HyperLink:
        selector = ByXPATH('//nx-system-settings-component//nx-menu//a[@id="users"]')
        return HyperLink(self._browser.wait_element(selector, 15))

    def add_user_button(self, timeout_sec=5) -> Button:
        xpath_quoted = ByXPATH.quoted("//nx-menu-button[@data-testid=%s]/button", "addUserBtn")
        return Button(self._browser.wait_element(xpath_quoted, timeout_sec))

    def get_user_with_email(self, email: str, timeout: float = 15) -> WebDriverElement:
        xpath = ByXPATH.quoted(
            "//nx-system-settings-component//nx-menu//nx-search-highlight[contains(text(), %s)]",
            email,
            )
        return self._browser.wait_element(xpath, timeout)

    def has_user_with_email(self, email: str) -> bool:
        try:
            self.get_user_with_email(email, timeout=1)
        except ElementNotFound:
            return False
        else:
            return True


class AddUserModal:

    def __init__(self, browser: Browser):
        self._browser = browser

    def _get_email_input(self) -> InputField:
        selector = ByXPATH("//nx-email-input[@id='addUserDialogEmail']//input")
        return InputField(self._browser.wait_element(selector, 5))

    def input_email_for_new_user(self, email: str):
        self._get_email_input().clear()
        self._get_email_input().put(email)
        # Hitting Tab is necessary or input will fail.
        self._browser.request_keyboard().send_keys(Keys.TAB)

    def get_add_user_button(self) -> Button:
        selector = ByXPATH("//form[@name='addUserForm']//*[@data-testid='addUserBtn']//button")
        return Button(self._browser.wait_element(selector, 5))

    def get_error_text(self) -> str:
        selector = ByXPATH("//span[contains(@class, 'input-error')]")
        return get_visible_text(self._browser.wait_element(selector, 5))

    def get_close_button(self) -> Button:
        selector = ByXPATH("//button[@data-testid='closeAddUser']")
        return Button(self._browser.wait_element(selector, 5))
