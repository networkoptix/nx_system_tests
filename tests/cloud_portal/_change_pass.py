# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.color import RGBColor
from browser.css_properties import get_borders_style
from browser.html_elements import Button
from browser.html_elements import InputField
from browser.webdriver import BoundingRectangle
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import ElementSelector
from browser.webdriver import VisibleElement
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us


class ChangePassForm:

    def __init__(self, browser: Browser):
        self._browser = browser

    def current_password_input(self) -> 'PasswordInput':
        selector = ByXPATH("//input[@id='password']")
        return PasswordInput(self._browser, selector)

    def new_password_input(self) -> 'PasswordInput':
        selector = ByXPATH("//nx-password-input[@componentid='newPassword']//input")
        return PasswordInput(self._browser, selector)

    def get_save_button(self) -> Button:
        selector = ByXPATH("//button[@type='submit']")
        return Button(self._browser.wait_element(selector, 10))

    def get_no_unsaved_changes_placeholder(self) -> VisibleElement:
        selector = ByXPATH("//div[contains(@class, 'placeholder-text-no-changes')]")
        return VisibleElement(self._browser.wait_element(selector, 10))


class PasswordInput:

    def __init__(self, browser: Browser, selector: ElementSelector):
        self._browser = browser
        self._input_selector = selector

    def _get_input_element(self) -> WebDriverElement:
        return self._browser.wait_element(self._input_selector, 10)

    def focus(self) -> None:
        self._get_input_element().invoke()

    def set_password(self, password: str) -> None:
        password_input = InputField(self._get_input_element())
        password_input.clear()
        password_input.put(password)

    def is_encircled_by(self, color: RGBColor) -> bool:
        return get_borders_style(self._get_input_element()).is_encircled_by(color)


class PasswordBadge:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_text(self) -> str:
        return get_visible_text(self._get_element())

    def _get_element(self) -> WebDriverElement:
        selector = ByXPATH("//nx-password-input-tag-validation//nx-tag//a")
        return self._browser.wait_element(selector, 10)

    def _get_bounding_rect(self) -> BoundingRectangle:
        return VisibleElement(self._get_element()).get_bounding_rect()

    def hover_over(self):
        self._browser.request_mouse().hover(
            self._get_bounding_rect().get_absolute_coordinates(0.5, 0.5),
            )


class PasswordTooltip:

    def __init__(self, browser: Browser):
        self._browser = browser

    def get_text(self) -> str:
        return get_visible_text(self._get_element())

    def _get_element(self) -> WebDriverElement:
        selector = ByXPATH("//nx-tooltip-component//div[contains(@class, 'tooltip-body')]")
        return self._browser.wait_element(selector, 10)


class SetNewPasswordForm:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def get_password_field(self) -> PasswordInput:
        selector = ByXPATH("//nx-password-input[@componentid='resetPassword']//input")
        return PasswordInput(self._browser, selector)

    def get_next_button(self) -> Button:
        text = self._translation_table.tr("NEXT")
        selector = ByXPATH.quoted(
            "//nx-authorize-reset-password-component//button[contains(text(), %s)]",
            text,
            )
        return Button(self._browser.wait_element(selector, 5))
