# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.html_elements import Button
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import VisibleElement
from browser.webdriver import get_visible_text
from tests.web_admin._nx_editable_name import EditableName


class SystemNameForm:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_editable_name(self) -> EditableName:
        xpath = "//nx-system-admin-component//form//nx-editable-heading[@id='systemName']"
        return EditableName(self._browser, ByXPATH(xpath))

    def get_permissions(self) -> VisibleElement:
        selector_value = (
            "//nx-system-admin-component"
            "//span[@data-testid='accessLevelText']"
            "/following-sibling::span[2]")
        return VisibleElement(self._browser.wait_element(ByXPATH(selector_value), 10))

    def get_merge_with_another_button(self) -> Button:
        xpath = (
            "//nx-system-admin-component"
            "//button[contains(., 'Merge with Another System')]"
            )
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))


def get_permissions_groups_tooltip_text(browser: Browser) -> str:
    selector = ByXPATH('//div[contains(@class, "cdk-overlay-container")]//nx-tooltip-component')
    tooltip_element = browser.wait_element(selector, 10)
    return get_visible_text(tooltip_element)
