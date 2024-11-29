# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Mapping

from browser.html_elements import Button
from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us
from tests.cloud_portal.elements.nx_checkbox import NxCheckbox


class AccountInformation:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def first_name_field(self) -> InputField:
        selector = ByXPATH("//input[@id='firstName']")
        return InputField(self._browser.wait_element(selector, 15))

    def last_name_field(self) -> InputField:
        selector = ByXPATH("//input[@id='lastName']")
        return InputField(self._browser.wait_element(selector, 5))

    def save(self) -> None:
        self.save_button().invoke()

    def save_button(self) -> Button:
        selector = ByXPATH.quoted(
            "//nx-account-settings-component//button[contains(text(), %s)]",
            self._translation_table.tr('SAVE_2'),
            )
        return Button(self._browser.wait_element(selector, 5))

    def cancel_button(self) -> Button:
        selector = ByXPATH.quoted(
            "//nx-account-settings-component//nx-cancel-button/button[contains(text(), %s)]",
            self._translation_table.tr('CANCEL_2'),
            )
        return Button(self._browser.wait_element(selector, 5))


class AccountSecurityComponent:

    def __init__(self, browser: Browser):
        self._browser = browser
        self._translation_table = en_us

    def wait_for_2fa_disabled_badge(self) -> None:
        text = self._translation_table.tr('DISABLED')
        selector = ByXPATH.quoted(
            "//nx-account-security-component//a[contains(text(), %s)]",
            text,
            )
        self._browser.wait_element(selector, 5)

    def wait_for_2fa_enabled_badge(self) -> None:
        text = self._translation_table.tr('ENABLED')
        selector = ByXPATH.quoted(
            "//nx-account-security-component//a[contains(text(), %s)]",
            text,
            )
        self._browser.wait_element(selector, 5)

    def get_enable_2fa_button(self) -> Button:
        text = self._translation_table.tr('ENABLE_2FA')
        selector = ByXPATH.quoted(
            "//nx-account-security-component//button[contains(text(), %s)]",
            text,
            )
        return Button(self._browser.wait_element(selector, 5))

    def get_disable_2fa_button(self) -> Button:
        text = self._translation_table.tr('DISABLE')
        selector = ByXPATH.quoted(
            "//nx-account-security-component//button[contains(text(), %s)]",
            text,
            )
        return Button(self._browser.wait_element(selector, 5))

    def _get_2fa_required_on_login_checkbox(self):
        return NxCheckbox(self._browser, ByXPATH("//nx-checkbox[@componentid='skip-tfauth']"))

    def turn_off_2fa_requirement_on_login(self) -> None:
        self._get_2fa_required_on_login_checkbox().uncheck()

    def twofa_is_required_on_every_login(self) -> bool:
        return self._get_2fa_required_on_login_checkbox().is_checked()


class AccountThemesComponent:

    def __init__(self, browser: Browser):
        self._browser = browser

    def select_dark_theme(self) -> None:
        selector = ByXPATH(
            "//nx-account-settings-component"
            "//nx-theme-switcher-component"
            "//svg-icon[contains(@data-src, 'dark.svg')]",
            )
        self._browser.wait_element(selector, 5).invoke()


class AccountLanguageDropDown:

    def __init__(self, browser: Browser):
        self._browser = browser

    def select_language(self, expected_language: str) -> None:
        language_dropdown_selector = ByXPATH('//*[@id="dropdownMenuButton"]')
        self._browser.wait_element(language_dropdown_selector, 5).invoke()
        languages = self._get_available_languages()
        for language, element in languages.items():
            if expected_language in language:
                element.invoke()
                return
        raise RuntimeError(
            f"Language {expected_language} is not among available languages: {languages.keys()}")

    def _get_available_languages(self) -> Mapping[str, WebDriverElement]:
        dropdown_menu = self._get_dropdown_element()
        language_entry_selector = ByXPATH(".//li[contains(@class, 'dropdown-item-container')]")
        language_elements = language_entry_selector.find_all_in(dropdown_menu)
        result = {}
        for language_element in language_elements:
            element_text = get_visible_text(language_element)
            result[element_text] = language_element
        return result

    def _get_dropdown_element(self) -> WebDriverElement:
        language_dropdown_selector = ByXPATH(
            "//nx-language-select//ul[contains(@class, 'dropdown-menu')]")
        return self._browser.wait_element(language_dropdown_selector, 5)
