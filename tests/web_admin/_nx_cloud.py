# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.html_elements import Button
from browser.html_elements import HyperLink
from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import get_visible_text


class NxCloudForm:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_cloud_host_link(self) -> HyperLink:
        xpath = "//h2[contains(text(),'Nx Cloud')]/ancestor::nx-block//a[@target='_blank']"
        return HyperLink(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_cloud_connect_link(self) -> HyperLink:
        xpath = "//h2[contains(text(),'Nx Cloud')]/ancestor::nx-block//nx-tag/a"
        return HyperLink(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_connect_to_cloud_button(self) -> Button:
        xpath = "//nx-system-admin-component//nx-process-button//button[@type='submit']"
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def system_has_connected_label(self) -> bool:
        xpath = "//nx-system-settings-component//nx-system-admin-component//nx-tag/a"
        return "CONNECTED" in get_visible_text(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_disconnect_from_cloud_button(self) -> Button:
        xpath = "//nx-system-admin-component//button[contains(.,'Disconnect from Nx Cloud')]"
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_owner_text(self) -> str:
        xpath = "//nx-system-admin-component//div[contains(@class, 'col-12') and contains(@class, 'pl-0')]"
        all_text = get_visible_text(self._browser.wait_element(ByXPATH(xpath), 10))
        [owner_text, _] = all_text.split('\n')
        return owner_text


class ConnectToCloudModal:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_title_text(self) -> str:
        selector = ByXPATH("//nx-modal-connect-cloud-content//h1")
        element = self._browser.wait_element(selector, 10)
        return get_visible_text(element)

    def get_connect_button(self) -> Button:
        xpath = "//nx-modal-connect-cloud-content//nx-process-button//button[contains(text(), %s)]"
        return Button(self._browser.wait_element(ByXPATH.quoted(xpath, "Connect"), 5))

    def get_password_input_field(self) -> InputField:
        selector = ByXPATH("//nx-modal-connect-cloud-content//input[@id='password']")
        return InputField(self._browser.wait_element(selector, 5))
