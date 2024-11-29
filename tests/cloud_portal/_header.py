# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
from typing import Mapping

from browser.html_elements import Button
from browser.html_elements import HyperLink
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us

_logger = logging.getLogger(__name__)


class HeaderNav:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def account_dropdown(self) -> Button:
        xpath = "//header//div[@data-testid='accountSettingsDropdown']/preceding-sibling::button"
        return Button(self._browser.wait_element(ByXPATH(xpath), timeout=15))

    def get_log_in_link(self) -> HyperLink:
        selector = ByXPATH("//header//nx-main-action//a[contains(@class, 'login')]")
        return HyperLink(self._browser.wait_element(selector, 10))

    def get_active_tab_name(self) -> str:
        selector = ByXPATH("//nx-header//div[contains(@class, 'active')]")
        return get_visible_text(self._browser.wait_element(selector, 10))

    def get_language_dropdown_button(self) -> Button:
        selector = ByXPATH("//nx-header-language-select//button[@id='dropdownMenuButton']")
        return Button(self._browser.wait_element(selector, 5))

    def get_systems_link(self) -> HyperLink:
        text = self._translation_table.tr('SYSTEMS_ENTRY_IN_HEADER_NAV')
        selector = ByXPATH.quoted("//nx-header//nx-header-level-one//a[contains(text(),%s)]", text)
        return HyperLink(self._browser.wait_element(selector, 10))

    def get_create_account_link(self) -> HyperLink:
        text = self._translation_table.tr('CREATE_ACCOUNT')
        selector = ByXPATH.quoted("//nx-header//a[contains(text(), %s)]", text)
        return HyperLink(self._browser.wait_element(selector, 5))

    def get_services_link(self) -> HyperLink:
        text = self._translation_table.tr('SERVICES')
        selector = ByXPATH.quoted('//nx-header-level-one//a[contains(text(), %s)]', text)
        return HyperLink(self._browser.wait_element(selector, 10))

    def wait_until_ready(self):
        # This method is used to ensure that header is loaded.
        selector = ByXPATH('//nx-header//nx-header-logo-area//img')
        self._browser.wait_element(selector, 30)


class AccountDropdownMenu:

    def __init__(self, browser: Browser):
        self._browser = browser

    def log_out_option(self) -> WebDriverElement:
        selector = ByXPATH("//header//li//a[@data-testid='logoutHeader']")
        return self._browser.wait_element(selector, 5)

    def account_settings_option(self) -> HyperLink:
        selector = ByXPATH("//header//li//a[@href='/account']")
        return HyperLink(self._browser.wait_element(selector, 10))

    def change_password_option(self) -> HyperLink:
        selector = ByXPATH("//header//li//a[@href='/account/password']")
        return HyperLink(self._browser.wait_element(selector, 10))

    def security_option(self) -> HyperLink:
        selector = ByXPATH("//header//li//a[@href = '/account/security']")
        return HyperLink(self._browser.wait_element(selector, 10))


class LanguageDropDownMenu:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_available_languages(self) -> Mapping[str, WebDriverElement]:
        dropdown_menu = self._get_dropdown_element()
        language_entry_selector = ByXPATH(".//li[contains(@class, 'dropdown-item-container')]")
        language_elements = language_entry_selector.find_all_in(dropdown_menu)
        result = {}
        for language_element in language_elements:
            element_text = get_visible_text(language_element)
            for language_code, text_pattern in _supported_languages.items():
                if text_pattern.match(element_text):
                    result[language_code] = language_element
                    break
            else:
                raise RuntimeError(f"An unknown language found: {element_text}")
        return result

    def _get_dropdown_element(self) -> WebDriverElement:
        language_dropdown_selector = ByXPATH("//nx-header-language-select//ul")
        return self._browser.wait_element(language_dropdown_selector, 5)


_supported_languages = {
    "en_US": re.compile(r'.*EN.*US.*'),
    "en_UK": re.compile(r'.*EN.*UK.*'),
    "de_DE": re.compile(r'.*DE.*Deutsch.*'),
    "ja_JP": re.compile(r'.*日本.*日本語.*'),
    }
