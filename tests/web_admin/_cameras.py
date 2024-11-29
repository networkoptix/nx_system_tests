# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from typing import Mapping

from browser.html_elements import Button
from browser.html_elements import HyperLink
from browser.html_elements import Img
from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text


class Camera:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_detailed_info_button(self) -> Button:
        selector = ByXPATH("//nx-cameras-component//button[@id='detailed-info']")
        return Button(self._browser.wait_element(selector, 10))

    def get_view_button(self) -> Button:
        selector = ByXPATH("//nx-cameras-component//button[@id='view-camera']")
        return Button(self._browser.wait_element(selector, 10))

    def get_aspect_ratio_button(self) -> Button:
        # The structure of a nx-section is built not upon a table, but sequence of DIVs,
        # what makes it difficult to use more straightforward XPATH.
        xpath = (
            "//nx-cameras-component"
            "//nx-section[.//h4[contains(text(), 'Image')]]"
            "//div[contains(@class, 'grid-container')]"
            "/div[2]"
            )
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_rotation_angle_button(self) -> Button:
        # The structure of a nx-section is built not upon a table, but sequence of DIVs,
        # what makes it difficult to use more straightforward XPATH.
        xpath = (
            "//nx-cameras-component"
            "//nx-section[.//h4[contains(text(), 'Image')]]"
            "//div[contains(@class, 'grid-container')]"
            "/div[4]"
            )
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_authentication_button(self) -> Button:
        selector = ByXPATH("//button[@id='update-credentials']")
        return Button(self._browser.wait_element(selector, 10))

    def get_preview_img(self) -> Img:
        selector = ByXPATH("//nx-cameras-component//div[contains(@class, 'camera-feed-img')]//img")
        return Img(self._browser.wait_element(selector, 10))


def get_aspect_ratios(browser: Browser) -> Mapping[str, WebDriverElement]:
    overlay_container = _get_overlay_container(browser)
    result = {}
    # 'nx-simple-dropdown-item' before
    # https://gitlab.nxvms.dev/dev/cloud_portal/-/commit/86830825305a19a7d244871f375451301efcd351
    # 'nx-select-item' after
    # TODO: Split the condition between 6.0 and 6.1+ branches after disappearance of
    #  https://artifactory.us.nxteam.dev/artifactory/build-vms-gitlab/master/39384/default/distrib/
    selector = ByXPATH(".//*[self::nx-simple-dropdown-item or self::nx-select-item]")
    for item in selector.find_all_in(overlay_container):
        item_text = get_visible_text(item)
        result[item_text] = item
    return result


def get_rotations(browser: Browser) -> Mapping[str, WebDriverElement]:
    overlay_container = _get_overlay_container(browser)
    result = {}
    # 'nx-simple-dropdown-item' before
    # https://gitlab.nxvms.dev/dev/cloud_portal/-/commit/86830825305a19a7d244871f375451301efcd351
    # 'nx-select-item' after
    # TODO: Split the condition between 6.0 and 6.1+ branches after disappearance of
    #  https://artifactory.us.nxteam.dev/artifactory/build-vms-gitlab/master/39384/default/distrib/
    selector = ByXPATH(".//*[self::nx-simple-dropdown-item or self::nx-select-item]")
    for item in selector.find_all_in(overlay_container):
        item_text = get_visible_text(item)
        result[item_text] = item
    return result


class CredentialsForm:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_login_input(self) -> InputField:
        xpath = "//div[@class='cdk-overlay-container']//input[@id='cameraLoginCredentials']"
        return InputField(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_password_input(self) -> InputField:
        xpath = "//div[@class='cdk-overlay-container']//input[@id='cameraPasswordCredentials']"
        return InputField(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_save_button(self) -> Button:
        xpath = "//div[@class='cdk-overlay-container']//nx-process-button//button[@type='submit']"
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_cancel_button(self) -> Button:
        xpath = "//div[@class='cdk-overlay-container']//nx-cancel-button/button"
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def wait_disappearance(self, timeout: float):
        timeout_at = time.monotonic() + timeout
        form_xpath = (
            "//div[@class='cdk-overlay-container']"
            "//form[.//span[contains(text(), 'Authentication Credentials')]]"
            )
        form_selector = ByXPATH(form_xpath)
        while True:
            try:
                self._browser.wait_element(form_selector, 0)
            except ElementNotFound:
                return
            if time.monotonic() > timeout_at:
                raise RuntimeError(f"Can't find element identified by {self}")
            time.sleep(0.5)


def _get_overlay_container(browser: Browser) -> WebDriverElement:
    return browser.wait_element(ByXPATH("//div[@class='cdk-overlay-container']"), 10)


class MotionDetectionSettings:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_settings_button(self) -> Button:
        selector = ByXPATH("//nx-motion-detection-settings//nx-three-dot//button")
        return Button(self._browser.wait_element(selector, 10))

    def get_enable_button(self) -> Button:
        selector = ByXPATH("//nx-motion-detection-settings//button[@id='enable-motion-detection']")
        return Button(self._browser.wait_element(selector, 10))

    def get_actions(self) -> Mapping[str, 'HyperLink']:
        list_selector = ByXPATH("//nx-motion-detection-settings//ul")
        list_element = self._browser.wait_element(list_selector, 10)
        result = {}
        for element in ByXPATH(".//a").find_all_in(list_element):
            name = get_visible_text(element)
            result[name] = HyperLink(element)
        return result
