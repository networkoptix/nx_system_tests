# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from abc import ABCMeta
from abc import abstractmethod
from typing import Mapping
from typing import Sequence

from browser.html_elements import Button
from browser.html_elements import HyperLink
from browser.html_elements import PreFormattedText
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text


class MonitoringMenu(metaclass=ABCMeta):

    @abstractmethod
    def get_server_choice_button(self) -> Button:
        pass

    @abstractmethod
    def get_graphs_link(self) -> HyperLink:
        pass

    @abstractmethod
    def get_logs_link(self) -> HyperLink:
        pass


class MonitoringMenuV1(MonitoringMenu):

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_server_choice_button(self) -> Button:
        selector = ByXPATH("//nx-monitoring//nx-select//button[@id='monitorAvailServersSelect']")
        return Button(self._browser.wait_element(selector, 10))

    def get_graphs_link(self) -> HyperLink:
        selector = ByXPATH("//nx-monitoring//nx-menu//a[@id='graphs']")
        return HyperLink(self._browser.wait_element(selector, 10))

    def get_logs_link(self) -> HyperLink:
        selector = ByXPATH("//nx-monitoring//nx-menu//a[@id='logs']")
        return HyperLink(self._browser.wait_element(selector, 10))


class MonitoringMenuV2(MonitoringMenu):

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_server_choice_button(self) -> Button:
        selector = ByXPATH("//nx-monitoring//nx-select-v2")
        return Button(self._browser.wait_element(selector, 10))

    def get_graphs_link(self) -> HyperLink:
        selector = ByXPATH("//nx-monitoring//nx-menu//a[@id='graphs']")
        return HyperLink(self._browser.wait_element(selector, 10))

    def get_logs_link(self) -> HyperLink:
        selector = ByXPATH("//nx-monitoring//nx-menu//a[@id='logs']")
        return HyperLink(self._browser.wait_element(selector, 10))


def get_monitoring_menu(browser: Browser) -> 'MonitoringMenu':
    page_version = _find_monitoring_page_version(browser, timeout=10)
    if page_version == 1:
        return MonitoringMenuV1(browser)
    elif page_version == 2:
        return MonitoringMenuV2(browser)
    raise RuntimeError(f"Unknown page version {page_version}")


def get_monitoring_graph(browser: Browser) -> '_MonitoringGraph':
    # SVG has a different from HTML namespace 'https://www.w3.org/2000/svg'
    # what prevents search by a tag name.
    graph_selector = ByXPATH("//nx-app//ngx-charts-chart/div/*[name()='svg']")
    return _MonitoringGraph(browser.wait_element(graph_selector, 10))


class _MonitoringGraph:

    def __init__(self, mutable_element: WebDriverElement):
        # The monitoring graph is mutable, so it could return
        # different values without raising StaleElementError.
        self._graph_element = mutable_element

    def get_lines(self) -> Sequence[str]:
        result = []
        for shape in ByXPATH(".//*[name()='path']").find_all_in(self._graph_element):
            result.append(shape.get_attribute("d"))
        return result


class SystemLogs:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_refresh_logger_button(self) -> Button:
        selector = ByXPATH("//nx-logs//nx-logger//footer//button[@id='refresh-logger']")
        return Button(self._browser.wait_element(selector, 10))

    def get_select_logger_button(self) -> Button:
        selector = ByXPATH("//nx-logs//nx-logger//nx-select//button[@id='log-levels']")
        return Button(self._browser.wait_element(selector, 10))

    def get_loggers(self) -> Mapping[str, HyperLink]:
        logger_xpath = (
            "//nx-logs//nx-logger//nx-select"
            "//div[@class='dropdown-menu' and @aria-labelledby='log-levels']")
        menu = self._browser.wait_element(ByXPATH(logger_xpath), 10)
        result = {}
        logger_selector = ByXPATH(".//a[contains(@class, 'dropdown-item')]")
        for logger_element in logger_selector.find_all_in(menu):
            logger_name = get_visible_text(logger_element)
            result[logger_name] = HyperLink(logger_element)
        return result

    def get_logger_element(self) -> PreFormattedText:
        selector = ByXPATH("//nx-logs//nx-logger//pre[@name='log-frame']")
        return PreFormattedText(self._browser.wait_element(selector, 10))


def _find_monitoring_page_version(browser: Browser, timeout: float) -> int:
    # TODO: After 01.08.2024 reaccess if the version condition is still needed
    # Monitoring page is going to be drastically refactored.
    # It may take some time to move to the new version.
    timeout_at = time.monotonic() + timeout
    v1_selector = ByXPATH("//nx-monitoring//nx-select[following-sibling::nx-menu]")
    v2_selector = ByXPATH("//nx-monitoring//nx-select-v2[following-sibling::nx-menu]")
    while True:
        try:
            browser.wait_element(v1_selector, 0.5)
        except ElementNotFound:
            try:
                browser.wait_element(v2_selector, 0.5)
            except ElementNotFound:
                if time.monotonic() > timeout_at:
                    raise RuntimeError(f"Can't find the page version after {timeout}")
                continue
            return 2
        return 1


def get_monitoring_servers(browser: Browser) -> Mapping[str, HyperLink]:
    page_version = _find_monitoring_page_version(browser, timeout=10)
    if page_version == 1:
        return _get_monitoring_servers_v1(browser)
    elif page_version == 2:
        return _get_monitoring_servers_v2(browser)
    raise RuntimeError(f"Unknown page version {page_version}")


def _get_monitoring_servers_v1(browser: Browser) -> Mapping[str, HyperLink]:
    menu_xpath = "//div[@class='dropdown-menu' and @aria-labelledby='monitorAvailServersSelect']"
    menu = browser.wait_element(ByXPATH(menu_xpath), 10)
    result = {}
    for server_element in ByXPATH(".//li//a[contains(@class, 'dropdown-item')]").find_all_in(menu):
        server_name = get_visible_text(server_element)
        result[server_name] = HyperLink(server_element)
    return result


def _get_monitoring_servers_v2(browser: Browser) -> Mapping[str, HyperLink]:
    menu_xpath = "//div[contains(@class, 'cdk-overlay-container')]"
    menu = browser.wait_element(ByXPATH(menu_xpath), 10)
    result = {}
    for server_element in ByXPATH(".//nx-select-item").find_all_in(menu):
        server_name = get_visible_text(server_element)
        result[server_name] = HyperLink(server_element)
    return result
