# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Mapping

from browser.html_elements import Video
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text


def get_server_entries(browser: Browser) -> Mapping[str, '_ServerMenuEntry']:
    server_list_element = browser.wait_element(ByXPATH("//div[@class='server-list']"), 10)
    result = {}
    for server_entry in ByXPATH(".//div[@class='server-name']").find_all_in(server_list_element):
        server_name = get_visible_text(server_entry)
        result[server_name] = _ServerMenuEntry(browser, server_name)
    return result


class _ServerMenuEntry:

    def __init__(self, browser: Browser, server_name: str):
        self._browser = browser
        self._server_name = server_name

    def is_expanded(self) -> bool:
        element = self._get_entry_element()
        return self._is_entry_expanded(element)

    def has_cameras(self) -> bool:
        element = self._get_entry_element()
        try:
            ByXPATH(".//svg-icon[contains(@class, 'expand')]").find_in(element)
        except ElementNotFound:
            return False
        return True

    def expand(self):
        element = self._get_entry_element()
        if not self._is_entry_expanded(element):
            element.invoke()

    def contract(self):
        element = self._get_entry_element()
        if self._is_entry_expanded(element):
            element.invoke()

    def get_camera_entries(self) -> Mapping[str, '_CameraEntry']:
        element = self._get_entry_element()
        result = {}
        selector = ByXPATH(".//a[contains(@class, 'camera') and contains(@href, '#/view')]")
        for camera_element in selector.find_all_in(element):
            href = camera_element.get_attribute('href')
            camera_url = get_visible_text(camera_element)
            _, camera_id = href.rsplit("/", maxsplit=1)
            result[camera_url] = _CameraEntry(self._browser, camera_id)
        return result

    def _get_entry_element(self) -> WebDriverElement:
        servers_element = self._browser.wait_element(ByXPATH("//div[@class='server-list']"), 10)
        entry_xpath = ".//nx-search-highlight//ancestor::div[contains(@class, 'server ')]"
        for server_entry_element in ByXPATH(entry_xpath).find_all_in(servers_element):
            server_name, *_camera_urls = get_visible_text(server_entry_element).split("\n")
            if server_name == self._server_name:
                return server_entry_element
        raise RuntimeError(f"Can't find {self._server_name}")

    @staticmethod
    def _is_entry_expanded(element: WebDriverElement) -> bool:
        return "expanded" in element.get_attribute("class")

    def __repr__(self):
        return f"<ViewPage: {self._server_name}>"


class _CameraEntry:

    def __init__(self, browser: Browser, id_: str):
        self._browser = browser
        self._id = id_

    def is_opened(self) -> bool:
        element = self._get_entry_element()
        return "selected" in element.get_attribute("class")

    def open(self):
        self._get_entry_element().invoke()

    def _get_entry_element(self) -> WebDriverElement:
        xpath_template = "//div[contains(@class, 'server-list')]//a[contains(@href, %s)]"
        selector = ByXPATH.quoted(xpath_template, self._id)
        return self._browser.wait_element(selector, 10)

    def __repr__(self):
        return f"<CameraMenuEntry: {self._id}>"


class CameraPreview:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_live(self) -> Video:
        xpath = "//nx-system-view-camera-page//nx-player-js//video"
        return Video(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_offline_placeholder(self) -> WebDriverElement:
        selector = ByXPATH("//nx-system-view-camera-page//nx-player-placeholder")
        return self._browser.wait_element(selector, 10)

    def get_archive_controls(self) -> WebDriverElement:
        controls_xpath = ByXPATH("//nx-system-view-camera-page//div[@class='controls']")
        return self._browser.wait_element(controls_xpath, 10)

    def get_live_camera_archive(self) -> WebDriverElement:
        selector = ByXPATH("//nx-system-view-camera-page//nx-timeline")
        return self._browser.wait_element(selector, 10)

    def get_empty_archive(self) -> WebDriverElement:
        xpath = (
            "//nx-system-view-camera-page"
            "//div[@class='controls']"
            "//span[contains(text(), 'No Archive')]"
            )
        return self._browser.wait_element(ByXPATH(xpath), 10)
