# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from datetime import date
from datetime import datetime
from typing import Collection
from typing import Mapping
from typing import NamedTuple
from typing import Optional

from browser.html_elements import Button
from browser.html_elements import HyperLink
from browser.html_elements import InputField
from browser.html_elements import Table
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import get_visible_text


class LicensesForm:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_channels_summary(self) -> Mapping[str, 'Channels']:
        licenses_table_selector = ByXPATH("//nx-license-summary-component//table")
        licenses_table = Table(self._browser.wait_element(licenses_table_selector, 5))
        result = {}
        for row in licenses_table.get_non_empty_rows():
            license_type_value = get_visible_text(row[0])
            channels_value = int(get_visible_text(row[1]))
            available_value = int(get_visible_text(row[2]))
            licenses_in_use_value = int(get_visible_text(row[3]))
            channels = Channels(channels_value, available_value, licenses_in_use_value)
            result[license_type_value] = channels
        return result

    def choose_server(self, name: str):
        self._click_server_select()
        self._select_server(name)

    def get_license_input(self) -> InputField:
        xpath = (
            "//nx-license-new-component//nx-block[.//header[contains(., 'New License')]]"
            "//input[@id='licenseKey']"
            )
        return InputField(self._browser.wait_element(ByXPATH(xpath), 5))

    def get_activate_button(self) -> Button:
        xpath = (
            "//nx-license-new-component//nx-block[.//header[contains(., 'New License')]]"
            "//button[@type='submit']"
            )
        return Button(self._browser.wait_element(ByXPATH(xpath), 5))

    def get_activate_free_licenses_button(self) -> Button:
        xpath = "//nx-license-trial-component//button[@type='submit']"
        return Button(self._browser.wait_element(ByXPATH(xpath), 5))

    def _click_server_select(self):
        server_selection = "//nx-select[@name='bindToServer']"
        server_select_menu = self._browser.wait_element(ByXPATH(server_selection), 5)
        server_select_menu.invoke()

    def _select_server(self, name: str):
        xpath_template = (
            "//nx-block[.//*[contains(text(), 'New License')]]"
            "//div[contains(@class, 'dropdown-menu')]"
            "//span[contains(text(), %s)]/parent::a"
            )
        server_link_xpath = ByXPATH.quoted(xpath_template, name)
        server_link = HyperLink(self._browser.wait_element(server_link_xpath, 5))
        server_link.invoke()


class Channels(NamedTuple):
    total: int
    available: int
    in_use: int


def get_active_keys_names_first(browser: Browser) -> Mapping['_ServerIdentifier', Collection['ActiveKey']]:
    result = {}
    license_keys_component = browser.wait_element(ByXPATH("//nx-license-detail-component"), 10)
    for license_key_element in ByXPATH(".//nx-block").find_all_in(license_keys_component):
        license_key_text = get_visible_text(license_key_element)
        if _is_permanent(license_key_text):
            [server_id, active_key] = _parse_permanent_key_names_first(license_key_text)
        else:
            [server_id, active_key] = _parse_temporary_key_names_first(license_key_text)
        result.setdefault(server_id, set()).add(active_key)
    return result


def get_active_keys_by_rows(browser: Browser) -> Mapping['_ServerIdentifier', Collection['ActiveKey']]:
    result = {}
    license_keys_component = browser.wait_element(ByXPATH("//nx-license-detail-component"), 10)
    for license_key_element in ByXPATH(".//nx-block").find_all_in(license_keys_component):
        license_key_text = get_visible_text(license_key_element)
        if _is_permanent(license_key_text):
            [server_id, active_key] = _parse_permanent_key_by_rows(license_key_text)
        else:
            [server_id, active_key] = _parse_temporary_key_by_rows(license_key_text)
        result.setdefault(server_id, set()).add(active_key)
    return result


def _is_permanent(key_info: str) -> bool:
    # Permanent keys do not have expiration time but deactivation counter instead.
    # They have different fields amount and structure as well.
    return "Deactivation left" in key_info


def _parse_permanent_key_names_first(text: str) -> tuple['_ServerIdentifier', 'ActiveKey']:
    [
        key_value,
        *_titles,
        channels,
        server_name,
        hardware_id,
        _status,
        expiration_datetime,
        _deactivations_left,
        ] = [field.strip() for field in text.split("\n")]
    try:
        datetime.strptime(expiration_datetime, "%d %b %Y, %I:%M %p")
    except ValueError:
        return (
            _ServerIdentifier(server_name, hardware_id),
            ActiveKey(key_value, int(channels), None),
            )
    raise RuntimeError(f"Permanent license has an expiration datetime: {expiration_datetime}")


def _parse_permanent_key_by_rows(text: str) -> tuple['_ServerIdentifier', 'ActiveKey']:
    [
        key_value,
        _type_title,
        _type,
        _channels_title,
        channels,
        _server_name_title,
        server_name,
        _hardware_id_title,
        hardware_id,
        _status_title,
        _status,
        _expiration_datetime_title,
        expiration_datetime,
        _deactivations_left_title,
        _deactivations_left,
        ] = [field.strip() for field in text.split("\n")]
    try:
        datetime.strptime(expiration_datetime, "%d %b %Y, %I:%M %p")
    except ValueError:
        return (
            _ServerIdentifier(server_name, hardware_id),
            ActiveKey(key_value, int(channels), None),
            )
    raise RuntimeError(f"Permanent license has an expiration datetime: {expiration_datetime}")


def _parse_temporary_key_names_first(text: str) -> tuple['_ServerIdentifier', 'ActiveKey']:
    [
        key_value,
        *_titles,
        channels,
        server_name,
        hardware_id,
        _status,
        expiration_datetime,
        ] = [field.strip() for field in text.split("\n")]
    expiration_datetime = datetime.strptime(expiration_datetime, "%d %b %Y, %I:%M %p")
    return (
        _ServerIdentifier(server_name, hardware_id),
        ActiveKey(key_value, int(channels), expiration_datetime.date()),
        )


def _parse_temporary_key_by_rows(text: str) -> tuple['_ServerIdentifier', 'ActiveKey']:
    [
        key_value,
        _type_title,
        _type,
        _channels_title,
        channels,
        _server_name_title,
        server_name,
        _hardware_id_title,
        hardware_id,
        _status_title,
        _status,
        _expiration_datetime_title,
        expiration_datetime,
        ] = [field.strip() for field in text.split("\n")]
    expiration_datetime = datetime.strptime(expiration_datetime, "%d %b %Y, %I:%M %p")
    return (
        _ServerIdentifier(server_name, hardware_id),
        ActiveKey(key_value, int(channels), expiration_datetime.date()),
        )


class ActiveKey(NamedTuple):
    value: str
    channels: int
    expires: Optional[date]


class _ServerIdentifier(NamedTuple):
    name: str
    id: str


_logger = logging.getLogger(__file__)
