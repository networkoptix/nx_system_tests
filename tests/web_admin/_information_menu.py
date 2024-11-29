# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.html_elements import HyperLink
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text


class InformationMenu:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_alerts_link(self) -> '_InformationMenuEntry':
        selector = ByXPATH("//div[contains(@class, 'gridMenu')]//nx-menu//a[@id='alerts']")
        return _InformationMenuEntry(self._browser.wait_element(selector, 10))

    def get_active_alerts_count(self) -> int:
        selector = ByXPATH(
            "//div[contains(@class, 'gridMenu')]//nx-menu//a[@id='alerts']//nx-alert-counter")
        return int(get_visible_text(self._browser.wait_element(selector, 10)))

    def get_systems_link(self) -> '_InformationMenuEntry':
        selector = ByXPATH("//div[contains(@class, 'gridMenu')]//nx-menu//a[@id='systems']")
        return _InformationMenuEntry(self._browser.wait_element(selector, 10))

    def get_servers_link(self) -> '_InformationMenuEntry':
        selector = ByXPATH("//div[contains(@class, 'gridMenu')]//nx-menu//a[@id='servers']")
        return _InformationMenuEntry(self._browser.wait_element(selector, 10))

    def get_storages_link(self) -> '_InformationMenuEntry':
        selector = ByXPATH("//div[contains(@class, 'gridMenu')]//nx-menu//a[@id='storages']")
        return _InformationMenuEntry(self._browser.wait_element(selector, 10))

    def get_network_interfaces_link(self) -> '_InformationMenuEntry':
        selector = ByXPATH(
            "//div[contains(@class, 'gridMenu')]//nx-menu//a[@id='networkInterfaces']")
        return _InformationMenuEntry(self._browser.wait_element(selector, 10))


class _InformationMenuEntry:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def invoke(self):
        self._element.invoke()

    def is_selected(self) -> bool:
        return "selected" in self._element.get_attribute("class")


def get_download_report_link(browser: Browser) -> HyperLink:
    # This hyperlink does not actually contain a URL to download a report.
    # Instead, it's invocation somehow constructs this report on the spot via JS.
    xpath = "//div[contains(@class, 'menuLinks')]//a[./svg-icon[contains(@data-src, 'download')]]"
    return HyperLink(browser.wait_element(ByXPATH(xpath), 10))


def get_reload_page_link(browser: Browser) -> HyperLink:
    xpath = "//div[contains(@class, 'menuLinks')]//a[./svg-icon[@title='Reload']]"
    return HyperLink(browser.wait_element(ByXPATH(xpath), 10))
