# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from typing import Sequence

from browser.html_elements import HyperLink
from browser.webdriver import Browser
from browser.webdriver import ByCSS
from browser.webdriver import ByXPATH
from browser.webdriver import ElementSelector
from browser.webdriver import StaleElementReference
from browser.webdriver import WebDriverElement


class MainMenu:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_licenses_link(self) -> HyperLink:
        return HyperLink(self._find_relevant(ByCSS("#licenses"), 10))

    def get_servers_link(self) -> HyperLink:
        return HyperLink(self._find_relevant(ByCSS("#servers"), 10))

    def get_system_administration_link(self) -> HyperLink:
        return HyperLink(self._find_relevant(ByCSS("#admin"), 10))

    def get_cameras_link(self) -> HyperLink:
        return HyperLink(self._find_relevant(ByCSS("#cameras"), 10))

    def get_users_link(self) -> HyperLink:
        return HyperLink(self._find_relevant(ByCSS("#users"), 10))

    def _find_relevant(self, selector: ElementSelector, timeout: float) -> WebDriverElement:
        # After changes in the WebAdmin aiming to ensure the Main Menu shows relevant system
        # status, the hyperlinks in the Main menu are re-created just after a page load process
        # starts which leads to appearance of StaleElementReference exceptions in further calls.
        # On top of that, the Main menu frame element is not changed, so it can't be used as an
        # indication if the menu is fully loaded.

        # See: https://gitlab.nxvms.dev/dev/nx/-/merge_requests/25342
        # See: https://gitlab.nxvms.dev/dev/cloud_portal/-/merge_requests/6440
        started_at = time.monotonic()
        result_element = self._browser.wait_element(selector, timeout)
        while True:
            time.sleep(1)
            try:
                result_element.http_get("/name")
            except StaleElementReference:
                now = time.monotonic()
                if now - started_at > timeout:
                    raise
                time_spent = now - started_at
                result_element = self._browser.wait_element(selector, timeout - time_spent)
                continue
            return result_element


def get_camera_entries(browser: Browser) -> Sequence['_CameraMenuEntry']:
    parent = browser.wait_element(ByXPATH("//div[@id='level3cameras']"), 10)
    camera_selector = ByXPATH(".//a[contains(@href, '/settings/cameras')]")
    camera_ids = []
    for camera_element in camera_selector.find_all_in(parent):
        camera_ids.append(camera_element.get_attribute("id"))
    return [_CameraMenuEntry(browser, camera_id) for camera_id in camera_ids]


class _CameraMenuEntry:

    def __init__(self, browser: Browser, camera_id: str):
        self._browser = browser
        self._id = camera_id

    def is_opened(self) -> bool:
        template = "//div[@id='level3cameras']//a[@id=%s]"
        element = self._browser.wait_element(ByXPATH.quoted(template, self._id), 10)
        class_attribute = element.get_attribute("class")
        return "selected" in class_attribute

    def open(self):
        camera_selector = ByXPATH.quoted("//div[@id='level3cameras']//a[@id=%s]", self._id)
        camera_element = self._browser.wait_element(camera_selector, 10)
        camera_element.invoke()

    def __repr__(self):
        return f'<Camera: {self._id}>'
