# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.html_elements import Button
from browser.webdriver import Browser
from browser.webdriver import ByXPATH


class NxApplyBar:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_save_button(self) -> Button:
        selector = ByXPATH("//nx-apply//nx-process-button//button[@type='submit']")
        return Button(self._browser.wait_element(selector, 10))

    def get_cancel_button(self) -> Button:
        selector = ByXPATH("//nx-apply//nx-cancel-button//button[@type='reset']")
        return Button(self._browser.wait_element(selector, 10))

    def wait_apply(self):
        no_changes_to_save = ByXPATH("//nx-apply//div[contains(text(), 'No unsaved changes')]")
        self._browser.wait_element(no_changes_to_save, 10)
