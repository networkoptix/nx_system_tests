# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Collection

from browser.html_elements import HyperLink
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import WebDriverElement
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us


class HistoryPage:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def get_releases_tab(self) -> '_Tab':
        text = self._translation_table.tr('RELEASES')
        selector = self._get_selector_for_tab(text)
        return _Tab(self._browser.wait_element(selector, 5))

    def get_patches_tab(self) -> '_Tab':
        text = self._translation_table.tr('PATCHES')
        selector = self._get_selector_for_tab(text)
        return _Tab(self._browser.wait_element(selector, 5))

    def get_betas_tab(self) -> '_Tab':
        text = self._translation_table.tr('BETAS')
        selector = self._get_selector_for_tab(text)
        return _Tab(self._browser.wait_element(selector, 5))

    def _get_selector_for_tab(self, text: str):
        return ByXPATH.quoted(
            '//nx-download-history//span[contains(@class,"tab-heading") '
            'and contains(text(), %s)]/parent::a',
            text,
            )

    def get_download_links(self) -> Collection['HyperLink']:
        outer_links = []
        download_links = []
        selector = ByXPATH('//div[@class="nx-tab-set-content"]')
        download_section = self._browser.wait_element(selector, 5)
        for link_element in ByXPATH(".//a").find_all_in(download_section):
            outer_links.append(link_element)
        for outer_element in outer_links:
            outer_element.invoke()
            for link_element in ByXPATH("following-sibling::ul//a").find_all_in(outer_element):
                download_links.append(HyperLink(link_element))
        return download_links


class _Tab:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def is_selected(self) -> bool:
        return "active" in self._element.get_attribute("class")

    def invoke(self) -> None:
        self._element.invoke()
