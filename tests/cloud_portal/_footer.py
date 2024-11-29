# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.html_elements import HyperLink
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us


class Footer:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def get_copyright_link(self) -> HyperLink:
        selector = ByXPATH('//nx-nav-footer//a[contains(@class, "copyright")]')
        return HyperLink(self._browser.wait_element(selector, 5))

    def get_link_by_text(self, text: str) -> HyperLink:
        selector = ByXPATH.quoted('//nx-nav-footer//a[contains(text(), %s)]', text)
        return HyperLink(self._browser.wait_element(selector, 5))
