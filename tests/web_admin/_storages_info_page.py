# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from enum import Enum

from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import WebDriverElement


class StoragesInfoTable:

    def __init__(self, browser: Browser):
        self._browser = browser

    def name_order(self) -> '_StoragesInfoTableOrder':
        info_table_element = self._get_info_table_element()
        selector = ByXPATH(".//thead//div[@title='Name']")
        return _StoragesInfoTableOrder(selector.find_in(info_table_element))

    def server_order(self) -> '_StoragesInfoTableOrder':
        info_table_element = self._get_info_table_element()
        selector = ByXPATH(".//thead//div[@title='Server']")
        return _StoragesInfoTableOrder(selector.find_in(info_table_element))

    def type_order(self) -> '_StoragesInfoTableOrder':
        info_table_element = self._get_info_table_element()
        selector = ByXPATH(".//thead//div[@title='Type']")
        return _StoragesInfoTableOrder(selector.find_in(info_table_element))

    def status_order(self) -> '_StoragesInfoTableOrder':
        info_table_element = self._get_info_table_element()
        selector = ByXPATH(".//thead//div[@title='Status']")
        return _StoragesInfoTableOrder(selector.find_in(info_table_element))

    def issues_order(self) -> '_StoragesInfoTableOrder':
        info_table_element = self._get_info_table_element()
        selector = ByXPATH(".//thead//div[contains(@title, 'Storage Issues (24h)')]")
        return _StoragesInfoTableOrder(selector.find_in(info_table_element))

    def read_rate_order(self) -> '_StoragesInfoTableOrder':
        info_table_element = self._get_info_table_element()
        selector = ByXPATH(".//thead//div[@title='Read Rate']")
        return _StoragesInfoTableOrder(selector.find_in(info_table_element))

    def write_rate_order(self) -> '_StoragesInfoTableOrder':
        info_table_element = self._get_info_table_element()
        selector = ByXPATH(".//thead//div[@title='Write Rate']")
        return _StoragesInfoTableOrder(selector.find_in(info_table_element))

    def total_space_order(self) -> '_StoragesInfoTableOrder':
        info_table_element = self._get_info_table_element()
        selector = ByXPATH(".//thead//div[@title='Total Space']")
        return _StoragesInfoTableOrder(selector.find_in(info_table_element))

    def vms_media_order(self) -> '_StoragesInfoTableOrder':
        info_table_element = self._get_info_table_element()
        selector = ByXPATH(".//thead//div[@title='Space Used by VMS media (%)']")
        return _StoragesInfoTableOrder(selector.find_in(info_table_element))

    def _get_info_table_element(self) -> WebDriverElement:
        selector = ByXPATH("//nx-system-metrics-component//div[@id='nx-table']//table")
        return self._browser.wait_element(selector, 10)


def get_storage_search_input(browser: Browser) -> InputField:
    selector = ByXPATH("//nx-system-metrics-component//nx-search//input[@name='query']")
    return InputField(browser.wait_element(selector, 10))


class _StoragesInfoTableOrder:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def set_ascending(self):
        self._enable()
        if self._get_current_status() == _StoragesTableOrderStatus.descending:
            self._element.invoke()

    def set_descending(self):
        self._enable()
        if self._get_current_status() == _StoragesTableOrderStatus.ascending:
            self._element.invoke()

    def _get_current_status(self) -> '_StoragesTableOrderStatus':
        status_xpath = ".//div[descendant::svg-icon and not(contains(@class, 'sort-dir'))]"
        status_div = ByXPATH(status_xpath).find_in(self._element)
        if "hidden" in status_div.get_attribute("style"):
            return _StoragesTableOrderStatus.not_set
        if status_div.get_attribute("class") == 'dynamic-table-show':
            return _StoragesTableOrderStatus.descending
        return _StoragesTableOrderStatus.ascending

    def _enable(self):
        if self._get_current_status() == _StoragesTableOrderStatus.not_set:
            self._element.invoke()


class _StoragesTableOrderStatus(Enum):
    not_set = "not_set"
    ascending = "ascending"
    descending = "descending"
