# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from typing import Mapping
from typing import NamedTuple
from typing import Sequence

from browser.html_elements import Button
from browser.html_elements import HyperLink
from browser.html_elements import Table
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text


class AlertsList:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_server_filter_button(self) -> Button:
        selector = ByXPATH("//nx-system-alerts-component//button[@id='server']")
        return Button(self._browser.wait_element(selector, 10))

    def get_devices_filter_button(self) -> Button:
        selector = ByXPATH("//nx-system-alerts-component//button[@id='deviceType']")
        return Button(self._browser.wait_element(selector, 10))

    def get_severity_filter_button(self) -> Button:
        selector = ByXPATH("//nx-system-alerts-component//button[@id='alertType']")
        return Button(self._browser.wait_element(selector, 10))

    def get_severities_filters(self) -> Mapping[str, '_Filter']:
        xpath = (
            "//nx-system-alerts-component//nx-select"
            "//div[contains(@class, 'dropdown-menu') and @aria-labelledby='alertType']"
            )
        menu_element = self._browser.wait_element(ByXPATH(xpath), 10)
        result = {}
        for alert_type_filter_element in ByXPATH(".//ul/li/a").find_all_in(menu_element):
            alert_type = get_visible_text(alert_type_filter_element)
            result[alert_type] = _Filter(alert_type_filter_element, self._browser)
        return result

    def get_devices_filters(self) -> Mapping[str, '_Filter']:
        xpath = (
            "//nx-system-alerts-component//nx-select"
            "//div[contains(@class, 'dropdown-menu') and @aria-labelledby='deviceType']"
            )
        menu_element = self._browser.wait_element(ByXPATH(xpath), 10)
        result = {}
        for device_type_filter_element in ByXPATH(".//ul/li/a").find_all_in(menu_element):
            device_type = get_visible_text(device_type_filter_element)
            result[device_type] = _Filter(device_type_filter_element, self._browser)
        return result

    def get_server_filters(self) -> Mapping[str, '_Filter']:
        xpath = (
            "//nx-system-alerts-component//nx-select"
            "//div[contains(@class, 'dropdown-menu') and @aria-labelledby='server']"
            )
        menu_element = self._browser.wait_element(ByXPATH(xpath), 10)
        result = {}
        for server_name_filter_element in ByXPATH(".//ul/li/a").find_all_in(menu_element):
            server_name = get_visible_text(server_name_filter_element)
            result[server_name] = _Filter(server_name_filter_element, self._browser)
        return result

    def get_active_alerts(self) -> Sequence['_Alert']:
        selector = ByXPATH("//nx-system-alerts-component//nx-dynamic-table")
        dynamic_table_element = self._browser.wait_element(selector, 10)
        return _AlertsTable(dynamic_table_element).get_active_alerts()

    def clear_filter_button(self) -> Button:
        xpath = "//nx-system-alerts-component//button[./span[contains(text(), 'Clear')]]"
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))


class _AlertsTable:

    def __init__(self, dynamic_table_element: WebDriverElement):
        self._element = dynamic_table_element

    def get_active_alerts(self) -> Sequence['_Alert']:
        timeout_at = time.monotonic() + 10
        while True:
            try:
                return self._get_active_alerts()
            except ElementNotFound:
                if time.monotonic() > timeout_at:
                    raise
                if self._is_empty():
                    return []
                time.sleep(0.2)

    def _get_active_alerts(self) -> Sequence['_Alert']:
        alerts_table = Table(ByXPATH(".//table").find_in(self._element))
        result = []
        for _alert_icon, alert_type, server, description in alerts_table.get_non_empty_rows():
            alert_type_text = get_visible_text(alert_type)
            server_name = get_visible_text(server)
            description_text = get_visible_text(description)
            result.append(_Alert(alert_type_text, server_name, description_text))
        return result

    def _is_empty(self) -> bool:
        try:
            ByXPATH(".//div[contains(text(), 'Nothing found')]").find_in(self._element)
        except ElementNotFound:
            return False
        return True


class _Filter:

    def __init__(self, filter_entry_element: WebDriverElement, browser: Browser):
        self._element = filter_entry_element
        self._browser = browser

    def apply(self):
        # Turned out that cells may be added to and removed from a table without its redrawing
        # leading to impossibility to tell definitely whether the alerts table has changed or not.
        # The most definite way to ensure the table redrawing is to open the information page
        # again after a filter is changed.
        # By unknown reasons, browser.refresh() may occasionally transfer to the #/settings
        current_url = self._browser.get_current_url()
        HyperLink(self._element).invoke()
        new_filter_url = self._retrieve_filter_url(current_url)
        self._browser.open(new_filter_url)

    def _retrieve_filter_url(self, url_before: str) -> str:
        timeout_sec = 10
        timeout_at = time.monotonic() + timeout_sec
        while True:
            url_after = self._browser.get_current_url()
            if url_after != url_before:
                return url_after
            if time.monotonic() > timeout_at:
                raise RuntimeError("Page url is not changed after filter change")
            time.sleep(0.3)


def get_servers_alerts_card(browser: Browser) -> '_ServerAlertsCard':
    xpath = (
        "//nx-system-alert-card-component[.//div[contains(text(), 'Servers')]]"
        "//div[contains(@class, 'card-body')]")
    card_text = get_visible_text(browser.wait_element(ByXPATH(xpath), 10))
    _offline, offline_counter, _warnings, warnings_counter = card_text.split("\n")
    return _ServerAlertsCard(int(offline_counter), int(warnings_counter))


def get_storage_locations_card(browser: Browser) -> '_StorageLocationCard':
    xpath = (
        "//nx-system-alert-card-component[.//div[contains(text(), 'Storage Locations')]]"
        "//div[contains(@class, 'card-body')]")
    card_text = get_visible_text(browser.wait_element(ByXPATH(xpath), 10))
    _errors, errors_counter, _warnings, warnings_counter = card_text.split("\n")
    return _StorageLocationCard(int(errors_counter), int(warnings_counter))


def get_network_interfaces_card(browser: Browser) -> '_NetworkInterfacesCard':
    xpath = (
        "//nx-system-alert-card-component[.//div[contains(text(), 'Network Interfaces')]]"
        "//div[contains(@class, 'card-body')]")
    card_text = get_visible_text(browser.wait_element(ByXPATH(xpath), 10))
    _errors, errors_counter, _warnings, warnings_counter = card_text.split("\n")
    return _NetworkInterfacesCard(int(errors_counter), int(warnings_counter))


class _StorageLocationCard(NamedTuple):
    errors: int
    warnings: int


class _NetworkInterfacesCard(NamedTuple):
    errors: int
    warnings: int


class _ServerAlertsCard(NamedTuple):
    offline: int
    warnings: int


class _Alert(NamedTuple):

    type: str
    server_name: str
    description: str
