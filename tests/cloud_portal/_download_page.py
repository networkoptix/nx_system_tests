# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.html_elements import HyperLink
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us


class DownloadsPage:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def get_windows_client_installer_hyperlink(self) -> HyperLink:
        selector = ByXPATH('//nx-download-component//a[@id="windows"]')
        return HyperLink(self._browser.wait_element(selector, 10))

    def get_linux_client_installer_hyperlink(self) -> HyperLink:
        selector = ByXPATH('//nx-download-component//a[@id="linux"]')
        return HyperLink(self._browser.wait_element(selector, 10))

    def get_mac_client_installer_hyperlink(self) -> HyperLink:
        selector = ByXPATH('//nx-download-component//a[@id="macos"]')
        return HyperLink(self._browser.wait_element(selector, 10))

    def get_play_store_hyperlink(self) -> HyperLink:
        selector = ByXPATH('//nx-download-component//a[contains(@class, "Android")]')
        return HyperLink(self._browser.wait_element(selector, 10))

    def get_itunes_store_hyperlink(self) -> HyperLink:
        selector = ByXPATH('//nx-download-component//a[contains(@class, "iOS")]')
        return HyperLink(self._browser.wait_element(selector, 10))

    def get_download_hyperlink(self) -> HyperLink:
        selector = ByXPATH('//nx-download-component//a[contains(@class, "download-button")]')
        return HyperLink(self._browser.wait_element(selector, 10))

    def get_other_releases_link(self) -> HyperLink:
        selector = ByXPATH('//a[@data-testid="historyReleaseLink"]')
        return HyperLink(self._browser.wait_element(selector, 10))
