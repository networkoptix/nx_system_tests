# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from typing import Mapping
from typing import NamedTuple

from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import get_visible_text


def get_system_info_cards_v60(browser: Browser) -> Mapping[str, '_SystemInfoCardV60']:
    xpath = "//nx-system-metrics-component//nx-single-entity//nx-section"
    card_text = get_visible_text(browser.wait_element(ByXPATH(xpath), 10))
    result = {}
    [
        *_column_names,
        system_name,
        servers_count,
        camera_channels_raw,
        storages,
        users,
        version,
        cloud_id_raw,
        ] = [field.strip() for field in card_text.split("\n")]
    result[system_name] = _SystemInfoCardV60(
        int(servers_count),
        int(camera_channels_raw) if camera_channels_raw.isdigit() else 0,
        int(storages),
        int(users),
        version,
        "" if cloud_id_raw == "_" else cloud_id_raw,
        )
    return result


def get_system_info_cards_v60x(browser: Browser) -> Mapping[str, '_SystemInfoCardV60']:
    xpath = "//nx-system-metrics-component//nx-single-entity//nx-section"
    card_text = get_visible_text(browser.wait_element(ByXPATH(xpath), 10))
    result = {}
    [
        *_column_names,
        system_name,
        _system_state,
        _services_added,
        _services_in_use,
        servers_count,
        camera_channels_raw,
        storages,
        users,
        version,
        cloud_id_raw,
        ] = [field.strip() for field in card_text.split("\n")]
    result[system_name] = _SystemInfoCardV60(
        int(servers_count),
        int(camera_channels_raw) if camera_channels_raw.isdigit() else 0,
        int(storages),
        int(users),
        version,
        "" if cloud_id_raw == "_" else cloud_id_raw,
        )
    return result


def get_system_info_cards_v61plus(browser: Browser) -> Mapping[str, '_SystemInfoCardV61Plus']:
    xpath = "//nx-system-metrics-component//nx-single-entity//nx-section"
    card_text = get_visible_text(browser.wait_element(ByXPATH(xpath), 10))
    result = {}
    [
        _system_name_title,
        system_name,
        _system_state_title,
        _system_state,
        _services_added_title,
        _services_added,
        _services_in_use_title,
        _services_in_use,
        _servers_count_title,
        servers_count,
        _camera_channels_title,
        camera_channels_raw,
        _storages_title,
        storages,
        _users_title,
        users,
        _version_title,
        version,
        _cloud_id_title,
        cloud_id_raw,
        _cloud_status_title,
        cloud_status_raw,
        ] = [field.strip() for field in card_text.split("\n")]
    result[system_name] = _SystemInfoCardV61Plus(
        int(servers_count),
        int(camera_channels_raw) if camera_channels_raw.isdigit() else 0,
        int(storages),
        int(users),
        version,
        "" if cloud_id_raw == "_" else cloud_id_raw,
        "" if cloud_status_raw == "_" else cloud_status_raw,
        )
    return result


class _SystemInfoCardV60(NamedTuple):
    servers: int
    camera_channels: int
    storages: int
    users: int
    version: str
    cloud_id: str


class _SystemInfoCardV61Plus(NamedTuple):
    servers: int
    camera_channels: int
    storages: int
    users: int
    version: str
    cloud_id: str
    cloud_status: str


_logger = logging.getLogger(__file__)
