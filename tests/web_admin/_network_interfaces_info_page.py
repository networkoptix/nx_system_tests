# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from enum import Enum

from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import WebDriverElement


class NetworkInterfacesInfoTable:

    def __init__(self, browser: Browser):
        self._browser = browser

    def name_order(self) -> '_NetworkInterfacesInfoTableOrder':
        info_table_element = self._get_table_element()
        selector = ByXPATH(".//thead//div[@title='Name']")
        return _NetworkInterfacesInfoTableOrder(selector.find_in(info_table_element))

    def server_order(self) -> '_NetworkInterfacesInfoTableOrder':
        info_table_element = self._get_table_element()
        selector = ByXPATH(".//thead//div[@title='Server']")
        return _NetworkInterfacesInfoTableOrder(selector.find_in(info_table_element))

    def state_order(self) -> '_NetworkInterfacesInfoTableOrder':
        info_table_element = self._get_table_element()
        selector = ByXPATH(".//thead//div[@title='State']")
        return _NetworkInterfacesInfoTableOrder(selector.find_in(info_table_element))

    def ip_order(self) -> '_NetworkInterfacesInfoTableOrder':
        info_table_element = self._get_table_element()
        selector = ByXPATH(".//thead//div[@title='IP']")
        return _NetworkInterfacesInfoTableOrder(selector.find_in(info_table_element))

    def in_rate_order(self) -> '_NetworkInterfacesInfoTableOrder':
        info_table_element = self._get_table_element()
        selector = ByXPATH(".//thead//div[@title='IN Rate']")
        return _NetworkInterfacesInfoTableOrder(selector.find_in(info_table_element))

    def out_rate_order(self) -> '_NetworkInterfacesInfoTableOrder':
        info_table_element = self._get_table_element()
        selector = ByXPATH(".//thead//div[@title='OUT Rate']")
        return _NetworkInterfacesInfoTableOrder(selector.find_in(info_table_element))

    def _get_table_element(self) -> WebDriverElement:
        selector = ByXPATH("//nx-system-metrics-component//div[@id='nx-table']//table")
        return self._browser.wait_element(selector, 10)


def get_interfaces_search_input(browser: Browser) -> InputField:
    selector = ByXPATH("//nx-system-metrics-component//nx-search//input[@name='query']")
    return InputField(browser.wait_element(selector, 10))


class _NetworkInterfacesInfoTableOrder:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def set_ascending(self):
        self._enable()
        if self._get_current_status() == _NetworkInterfacesTableOrderStatus.descending:
            self._element.invoke()

    def set_descending(self):
        self._enable()
        if self._get_current_status() == _NetworkInterfacesTableOrderStatus.ascending:
            self._element.invoke()

    def _get_current_status(self) -> '_NetworkInterfacesTableOrderStatus':
        status_xpath = ".//div[descendant::svg-icon and not(contains(@class, 'sort-dir'))]"
        status_div = ByXPATH(status_xpath).find_in(self._element)
        if "hidden" in status_div.get_attribute("style"):
            return _NetworkInterfacesTableOrderStatus.not_set
        if status_div.get_attribute("class") == 'dynamic-table-show':
            return _NetworkInterfacesTableOrderStatus.descending
        return _NetworkInterfacesTableOrderStatus.ascending

    def _enable(self):
        if self._get_current_status() == _NetworkInterfacesTableOrderStatus.not_set:
            self._element.invoke()


class _NetworkInterfacesTableOrderStatus(Enum):
    not_set = "not_set"
    ascending = "ascending"
    descending = "descending"
