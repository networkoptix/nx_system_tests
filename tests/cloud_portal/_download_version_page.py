# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Collection

from browser.html_elements import HyperLink
from browser.html_elements import VisibleElement
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us


class DownloadsVersion:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def get_version_title(self) -> VisibleElement:
        selector = ByXPATH('//h1[contains(@class, "title")]')
        return VisibleElement(self._browser.wait_element(selector, 10))

    def get_release_notes_headers(self) -> Collection[str]:
        release_notes_headers = []
        text = self._translation_table.tr("RELEASE_NOTES")
        selector = ByXPATH.quoted(
            '//nx-release//h4[contains(text(), %s)]/following-sibling::div/ul',
            text,
            )
        release_notes = self._browser.wait_element(selector, 5)
        for section in ByXPATH("./li").find_all_in(release_notes):
            release_notes_headers.append(VisibleElement(section).get_text().strip(":"))
        return release_notes_headers

    def get_download_links(self) -> Collection['HyperLink']:
        download_links = []
        text = self._translation_table.tr('DOWNLOAD_LINKS')
        selector = ByXPATH.quoted("//h4[contains(text(), %s)]", text)
        download_section = self._browser.wait_element(selector, 5)
        for outer_element in ByXPATH("following-sibling::div/a").find_all_in(download_section):
            outer_element.invoke()
            for link_element in ByXPATH("following-sibling::ul//a").find_all_in(outer_element):
                download_links.append(HyperLink(link_element))
        return download_links
