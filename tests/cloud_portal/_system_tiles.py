# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from abc import ABCMeta
from abc import abstractmethod

from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us


class _BaseSystemTiles(metaclass=ABCMeta):

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    @abstractmethod
    def _get_overlay_container(self) -> WebDriverElement:
        pass

    @abstractmethod
    def wait_for_systems_label(self) -> None:
        pass

    @abstractmethod
    def get_system_tile(self, expected_name: str, timeout: float = 10) -> '_SystemTile':
        pass

    def has_system_tile(self, system_name: str) -> bool:
        try:
            self.get_system_tile(system_name, timeout=2)
        except ElementNotFound:
            return False
        else:
            return True


class SystemTiles(_BaseSystemTiles):

    def _get_overlay_container(self) -> WebDriverElement:
        return self._browser.wait_element(ByXPATH("//nx-systems-list-component"), 20)

    def wait_for_systems_label(self, timeout: float = 10) -> None:
        element = ByXPATH.quoted(
            "//nx-systems-list-component//h1/span[contains(text(), %s)]",
            self._translation_table.tr("SYSTEMS_LABEL"),
            )
        self._browser.wait_element(element, timeout)

    def get_system_tile(self, expected_name: str, timeout: float = 10) -> '_SystemTile':
        started_at = time.monotonic()
        overlay_container = self._get_overlay_container()
        while True:
            for item in ByXPATH(".//nx-system-card").find_all_in(overlay_container):
                system_tile_name = get_visible_text(ByXPATH(".//h2//nx-search-highlight").find_in(item))
                if expected_name == system_tile_name:
                    return _SystemTile(self._browser, item)
            if time.monotonic() - started_at > timeout:
                raise ElementNotFound(f"No tile of system {expected_name} found")
            _logger.debug("Tile of system %s not found yet. Waiting", expected_name)
            time.sleep(0.5)


class ChannelPartnerSystemTiles(_BaseSystemTiles):

    def _get_overlay_container(self) -> WebDriverElement:
        return self._browser.wait_element(ByXPATH("//nx-groups-systems"), 20)

    def wait_for_systems_label(self) -> None:
        element = ByXPATH.quoted(
            "//nx-groups-systems//h1/span[contains(text(), %s)]",
            self._translation_table.tr("SYSTEMS_LABEL"),
            )
        self._browser.wait_element(element, 10)

    def get_system_tile(self, expected_name: str, timeout: float = 10) -> '_ChannelPartnerSystemTile':
        started_at = time.monotonic()
        overlay_container = self._get_overlay_container()
        while True:
            for item in ByXPATH(".//nx-card").find_all_in(overlay_container):
                system_tile_name = get_visible_text(ByXPATH(".//nx-search-highlight").find_in(item))
                if expected_name == system_tile_name:
                    return _ChannelPartnerSystemTile(self._browser, item)
            if time.monotonic() - started_at > timeout:
                raise ElementNotFound(f"No tile of system {expected_name} found")
            _logger.debug("Tile of system %s not found yet. Waiting", expected_name)
            time.sleep(0.5)


class _BaseSystemTile(metaclass=ABCMeta):

    def __init__(
            self,
            browser: Browser,
            tile_element: WebDriverElement,
            translation_table: TranslationTable = en_us,
            ):
        self._browser = browser
        self._element = tile_element
        self._translation_table = translation_table

    @abstractmethod
    def owner_name(self) -> str:
        pass

    def get_lock_icon(self) -> WebDriverElement:
        selector = ".//*[contains(@data-src, 'images/icons/standard/lock.svg')]"
        return ByXPATH(selector).find_in(self._element)

    @abstractmethod
    def has_open_button(self) -> bool:
        pass

    def has_offline_label(self, timeout: float) -> bool:
        started_at = time.monotonic()
        offline_text = self._translation_table.tr('OFFLINE_BADGE')
        badge_selector = ByXPATH.quoted(".//nx-tag//a[contains(text(), %s)]", offline_text)
        while True:
            try:
                badge_selector.find_in(self._element)
            except ElementNotFound:
                if time.monotonic() - started_at > timeout:
                    return False
                _logger.debug("Tile is not offline yet")
            else:
                return True
            time.sleep(2)

    @abstractmethod
    def wait_until_is_online(self, timeout: float) -> None:
        pass

    def click(self) -> None:
        self._element.invoke()


class _SystemTile(_BaseSystemTile):

    def owner_name(self) -> str:
        owner_label = ByXPATH(".//span[contains(@class, 'user-name')]").find_in(self._element)
        return get_visible_text(owner_label)

    def has_open_button(self) -> bool:
        try:
            ByXPATH(".//button").find_in(self._element)
        except ElementNotFound:
            return False
        else:
            return True

    def wait_until_is_online(self, timeout: float) -> None:
        started_at = time.monotonic()
        while True:
            if self.has_open_button():
                return
            if time.monotonic() - started_at > timeout:
                raise RuntimeError("Tile is offline after timeout")
            _logger.debug("Tile is not online yet. Waiting")
            time.sleep(0.5)


class _ChannelPartnerSystemTile(_BaseSystemTile):

    def owner_name(self) -> str:
        raise NotImplementedError("There's no owner name on Channel Partner system tile")

    def has_open_button(self) -> bool:
        raise NotImplementedError("There is no open button on Channel Partner system tile")

    def wait_until_is_online(self, timeout: float) -> None:
        started_at = time.monotonic()
        while True:
            if not self.has_offline_label(timeout=0):
                return
            if time.monotonic() - started_at > timeout:
                raise RuntimeError("Tile is offline after timeout")
            _logger.debug("Tile is not online yet. Waiting")
            time.sleep(0.5)


_logger = logging.getLogger(__name__)
