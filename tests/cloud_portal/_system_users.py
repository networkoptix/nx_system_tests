# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from browser.html_elements import Button
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us
from tests.cloud_portal.elements.nx_checkbox import NxCheckbox
from tests.cloud_portal.elements.nx_switch import NxSwitch


class SystemUsers:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def remove_user_button(self) -> Button:
        xpath = "//nx-system-user-component//button[contains(text(), 'Remove User')]"
        return Button(self._browser.wait_element(ByXPATH(xpath), 5))

    def remove_user_modal_button(self) -> Button:
        xpath_quoted = ByXPATH.quoted(
            "//nx-modal-remove-user-content//button[contains(text(),%s)]",
            "Remove",
            )
        return Button(self._browser.wait_element(xpath_quoted, 5))

    def wait_until_remove_modal_disappears(self) -> None:
        timeout_sec = 10
        started_at = time.monotonic()
        while True:
            try:
                self._browser.wait_element(ByXPATH("//nx-modal-remove-user-content"), 1)
            except ElementNotFound:
                return
            if time.monotonic() - started_at > timeout_sec:
                raise RuntimeError(
                    f"Remove user modal window is still visible within {timeout_sec} seconds")
            time.sleep(0.5)

    def save_button(self) -> Button:
        text = self._translation_table.tr('SAVE_2')
        xpath_quoted = ByXPATH.quoted("//button[text()=%s]", text)
        return Button(self._browser.wait_element(xpath_quoted, 5))

    def no_unsaved_changes(self) -> WebDriverElement:
        text = self._translation_table.tr('NO_UNSAVED_CHANGES')
        xpath_quoted = ByXPATH.quoted("//nx-apply//div[contains(text(),%s)]", text)
        return self._browser.wait_element(xpath_quoted, 10)

    def get_warning_message(self) -> str:
        selector = ByXPATH("//nx-system-user-component//span[contains(@class,'text-danger')]")
        return get_visible_text(self._browser.wait_element(selector, 5))

    def get_username_text(self) -> str:
        selector = ByXPATH("//nx-system-user-component//span[contains(@class,'user-name')]")
        return get_visible_text(self._browser.wait_element(selector, 5))

    def get_user_header_text(self) -> str:
        selector = ByXPATH("//nx-system-user-component//div[contains(@class, 'header-username')]")
        return get_visible_text(self._browser.wait_element(selector, 5))


class PermissionsOption6X:

    def __init__(self, browser: Browser, selector_string: str):
        self._browser = browser
        self._element = self._browser.wait_element(ByXPATH(selector_string), 2)
        self._checkbox = NxCheckbox(
            self._browser, ByXPATH(f"{selector_string}/preceding-sibling::nx-checkbox"))

    def is_selected(self) -> bool:
        return self._checkbox.is_checked()

    def select(self) -> None:
        if self.is_selected():
            _logger.debug("Option is already selected")
        else:
            self._element.invoke()

    def unselect(self) -> None:
        if not self.is_selected():
            _logger.debug("Option is already unselected")
        else:
            self._element.invoke()


class PermissionsOption51:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def is_selected(self) -> bool:
        return "selected" in self._element.get_attribute("class")

    def select(self) -> None:
        if self.is_selected():
            _logger.debug("Option is already selected")
        else:
            self._element.invoke()


class PermissionsDropdown:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_permissions_dropdown_button(self) -> Button:
        return Button(self._browser.wait_element(
            ByXPATH("//nx-system-user-component//button[@data-toggle='dropdown']"), 5))

    def get_power_users_option(self) -> PermissionsOption6X:
        selector_string = "//nx-multi-select//label[contains(text(), 'Power Users')]"
        return PermissionsOption6X(self._browser, selector_string)

    def get_administrator_option(self) -> PermissionsOption51:
        element = self._browser.wait_element(
            ByXPATH("//nx-permissions-select//a[contains(., 'Administrator')]"), 2)
        return PermissionsOption51(element)

    def get_viewer_6x_option(self) -> PermissionsOption6X:
        selector_string = "//nx-multi-select//label[text()='Viewers']"
        return PermissionsOption6X(self._browser, selector_string)

    def get_viewer_51_option(self) -> PermissionsOption51:
        element = self._browser.wait_element(
            ByXPATH("//nx-permissions-select//a[./span[text()='Viewer']]"), 2)
        return PermissionsOption51(element)

    def get_permissions_dropdown_text(self) -> str:
        selector = ByXPATH("//nx-system-user-component//button[@data-toggle='dropdown']")
        return get_visible_text(self._browser.wait_element(selector, 5))


class UserStatusSwitch:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_user_status_switch(self) -> NxSwitch:
        return NxSwitch(self._browser, ByXPATH("//nx-switch[@id='user-active-status']"))


_logger = logging.getLogger(__name__)
