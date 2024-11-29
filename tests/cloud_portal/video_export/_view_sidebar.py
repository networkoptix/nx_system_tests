# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from typing import Sequence

from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text


class ViewSidebar:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_server_camera_list(self, server_name: str) -> '_ServerCameraList':
        highlight_selector = ByXPATH.quoted(
            "//div[@class='server-list']//nx-search-highlight[text()=%s]",
            server_name)
        return _ServerCameraList(self._browser.wait_element(highlight_selector, 5))


class _ServerCameraList:

    def __init__(self, highlight_element: WebDriverElement):
        self._highlight_element = highlight_element

    def get_camera_thumbnail(self, camera_name: str) -> '_CameraThumbnail':
        for thumbnail in self._list_camera_thumbnails():
            if thumbnail.get_name() == camera_name:
                return thumbnail
        raise ElementNotFound(f"No thumbnail for camera with name {camera_name} found")

    def _list_camera_thumbnails(self) -> Sequence['_CameraThumbnail']:
        self._expand()
        camera_selector = ByXPATH(".//a[contains(@class, 'camera')]")
        expandable_element = self._get_expandable_element()
        camera_elements = camera_selector.find_all_in(expandable_element)
        return [_CameraThumbnail(camera_element) for camera_element in camera_elements]

    def _expand(self) -> None:
        if 'expanded' in self._get_expandable_element().get_attribute('class'):
            return
        self._highlight_element.invoke()

    def _get_expandable_element(self) -> WebDriverElement:
        return ByXPATH("../../..").find_in(self._highlight_element)


class _CameraThumbnail:

    def __init__(self, element: WebDriverElement):
        self._element = element

    def get_name(self) -> str:
        name_element = ByXPATH(
            "./span[contains(@class, 'name')]/nx-search-highlight").find_in(self._element)
        return get_visible_text(name_element)

    def select(self) -> None:
        self._element.invoke()
