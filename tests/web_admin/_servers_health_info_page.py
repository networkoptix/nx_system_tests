# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from enum import Enum

from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text


class ServersInfoTable:

    def __init__(self, browser: Browser):
        self._browser = browser

    def name_order(self) -> '_ServerInfoTableOrder':
        info_table_element = self._get_servers_info_element()
        selector = ByXPATH(".//thead//div[@title='Name']")
        return _ServerInfoTableOrder(selector.find_in(info_table_element))

    def status_order(self) -> '_ServerInfoTableOrder':
        info_table_element = self._get_servers_info_element()
        selector = ByXPATH(".//thead//div[@title='Status']")
        return _ServerInfoTableOrder(selector.find_in(info_table_element))

    def offline_events_order(self) -> '_ServerInfoTableOrder':
        info_table_element = self._get_servers_info_element()
        selector = ByXPATH(".//thead//div[contains(@title, 'Server Offline (24h)')]")
        return _ServerInfoTableOrder(selector.find_in(info_table_element))

    def uptime_order(self) -> '_ServerInfoTableOrder':
        info_table_element = self._get_servers_info_element()
        selector = ByXPATH(".//thead//div[@title='Uptime']")
        return _ServerInfoTableOrder(selector.find_in(info_table_element))

    def cpu_load_order(self) -> '_ServerInfoTableOrder':
        info_table_element = self._get_servers_info_element()
        selector = ByXPATH(".//thead//div[@title='Total CPU Usage (%)']")
        return _ServerInfoTableOrder(selector.find_in(info_table_element))

    def vms_cpu_load_order(self) -> '_ServerInfoTableOrder':
        info_table_element = self._get_servers_info_element()
        selector = ByXPATH(".//thead//div[@title='CPU used by VMS Server (%)']")
        return _ServerInfoTableOrder(selector.find_in(info_table_element))

    def ram_order(self) -> '_ServerInfoTableOrder':
        info_table_element = self._get_servers_info_element()
        selector = ByXPATH(".//thead//div[@title='Total RAM Usage (%)']")
        return _ServerInfoTableOrder(selector.find_in(info_table_element))

    def vms_ram_order(self) -> '_ServerInfoTableOrder':
        info_table_element = self._get_servers_info_element()
        selector = ByXPATH(".//thead//div[@title='RAM used by VMS Server (%)']")
        return _ServerInfoTableOrder(selector.find_in(info_table_element))

    def public_ip_order(self) -> '_ServerInfoTableOrder':
        info_table_element = self._get_servers_info_element()
        selector = ByXPATH(".//thead//div[@title='Public IP']")
        return _ServerInfoTableOrder(selector.find_in(info_table_element))

    def os_time_order(self) -> '_ServerInfoTableOrder':
        info_table_element = self._get_servers_info_element()
        selector = ByXPATH(".//thead//div[@title='OS Time']")
        return _ServerInfoTableOrder(selector.find_in(info_table_element))

    def time_changed_events_order(self) -> '_ServerInfoTableOrder':
        info_table_element = self._get_servers_info_element()
        selector = ByXPATH(".//thead//div[contains(@title, 'Time Changed (24h)')]")
        return _ServerInfoTableOrder(selector.find_in(info_table_element))

    def _get_servers_info_element(self) -> WebDriverElement:
        selector = ByXPATH("//nx-system-metrics-component//div[@id='nx-table']//table")
        return self._browser.wait_element(selector, 10)


def get_server_search_input(browser: Browser) -> InputField:
    selector = ByXPATH("//nx-system-metrics-component//nx-search//input[@name='query']")
    return InputField(browser.wait_element(selector, 10))


class _ServerInfoTableOrder:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def set_ascending(self):
        self._enable()
        if self._get_current_status() == _ServerTableOrderStatus.descending:
            self._element.invoke()

    def set_descending(self):
        self._enable()
        if self._get_current_status() == _ServerTableOrderStatus.ascending:
            self._element.invoke()

    def _get_current_status(self) -> '_ServerTableOrderStatus':
        status_xpath = ".//div[descendant::svg-icon and not(contains(@class, 'sort-dir'))]"
        status_div = ByXPATH(status_xpath).find_in(self._element)
        if "hidden" in status_div.get_attribute("style"):
            return _ServerTableOrderStatus.not_set
        if status_div.get_attribute("class") == 'dynamic-table-show':
            return _ServerTableOrderStatus.descending
        return _ServerTableOrderStatus.ascending

    def _enable(self):
        if self._get_current_status() == _ServerTableOrderStatus.not_set:
            self._element.invoke()


class _ServerTableOrderStatus(Enum):
    not_set = "not_set"
    ascending = "ascending"
    descending = "descending"


def get_server_card(browser: Browser) -> '_ServerCard':
    selector = ByXPATH("//nx-dynamic-table-panel-component//nx-block")
    return _ServerCard(browser.wait_element(selector, 10))


class _ServerCard:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def get_server_name(self) -> str:
        return get_visible_text(ByXPATH(".//header").find_in(self._element))
