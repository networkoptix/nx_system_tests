# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from browser.html_elements import Button
from browser.html_elements import HyperLink
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import WebDriverElement
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us

_logger = logging.getLogger(__name__)


class IPVDPage:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def get_advanced_search_button(self, wait_timeout: float = 5.0) -> Button:
        label = self._translation_table.tr("ADVANCED_SEARCH_BUTTON_TEXT")
        selector = ByXPATH.quoted("//span[text()=%s]", label)
        return Button(self._browser.wait_element(selector, wait_timeout))

    def get_devices_pane(self, wait_timeout: float = 5.0) -> WebDriverElement:
        label = self._translation_table.tr("DEVICES")
        selector = ByXPATH.quoted("//nx-block[@id='cameras-block']//span[@translate and text()=%s]", label)
        return self._browser.wait_element(selector, wait_timeout)

    def get_manufacturers_pane(self, wait_timeout: float = 5.0) -> WebDriverElement:
        label = self._translation_table.tr("MANUFACTURERS")
        selector = ByXPATH.quoted("//nx-block[@id='vendors-block']//span[@translate and text()=%s]", label)
        return self._browser.wait_element(selector, wait_timeout)

    def get_search_icon(self) -> HyperLink:
        selector = ByXPATH("//span[@class='glyphicon web-icon-search icon-search']")
        return HyperLink(self._browser.wait_element(selector, 10.0))

    def get_submit_request_link(self) -> HyperLink:
        label = self._translation_table.tr("SUBMIT_A_REQUEST")
        xpath_template = (
            "//span[contains(@class, 'pseudo-anchor') and "
            "contains(@class, 'ng-star-inserted') and "
            "text()=%s]"
            )
        selector = ByXPATH.quoted(xpath_template, label)
        return HyperLink(self._browser.wait_element(selector, 10.0))

    def get_cloud_logo(self) -> WebDriverElement:
        selector = ByXPATH("//nx-header//img[@src='/static/images/dark_logo.png']")
        return self._browser.wait_element(selector, 20.0)
