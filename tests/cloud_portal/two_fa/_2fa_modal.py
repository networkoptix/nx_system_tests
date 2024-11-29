# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from collections.abc import Collection

from browser.html_elements import Button
from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import ByXPATH
from browser.webdriver import VisibleElement
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text

_logger = logging.getLogger(__name__)


class EnableTwoFAModal:

    def __init__(self, browser: Browser):
        self._browser = browser

    def submit_password(self, password: str) -> None:
        password_selector = ByXPATH("//nx-enable-account-2fa//input[@type='password']")
        input_field = InputField(self._browser.wait_element(password_selector, 5))
        input_field.put(password)
        button_selector = ByXPATH("//nx-enable-account-2fa//button[@type='submit']")
        Button(self._browser.wait_element(button_selector, 5)).invoke()

    def get_qr_code(self) -> WebDriverElement:
        selector = ByXPATH("//*[@id='qrBadge']/qr-code")
        return self._browser.wait_element(selector, 5)

    def get_switch_key_mode_button(self) -> Button:
        selector = ByXPATH("//nx-enable-account-2fa//button[@id='qrMode']")
        return Button(self._browser.wait_element(selector, 2))

    def get_backup_codes(self) -> Collection[str]:
        backup_codes = []
        selector = ByXPATH('//div[@class="nx-backup-codes"]')
        backup_codes_section = self._browser.wait_element(selector, timeout=15)
        for code_element in ByXPATH("./div").find_all_in(backup_codes_section):
            code = get_visible_text(code_element)
            code = code[1:]  # The first digit is an index
            backup_codes.append(code)
        return backup_codes

    def move_to_next_step(self) -> None:
        selector = ByXPATH("//nx-enable-account-2fa//button[@id='nextWizardCode']")
        Button(self._browser.wait_element(selector, 5)).invoke()

    def get_twofa_key(self) -> str:
        selector = ByXPATH(
            "//nx-enable-account-2fa//nx-info-block"
            "//div[contains(@class, 'value')]//p[contains(@title,'Key')]")
        return VisibleElement(self._browser.wait_element(selector, 10)).get_text().strip()

    def submit_totp_code(self, code: str) -> None:
        input_selector = ByXPATH("//nx-2fa-code-input/input")
        InputField(self._browser.wait_element(input_selector, 5)).put(code)
        button_selector = ByXPATH("//nx-enable-account-2fa//button[@type='submit']")
        Button(self._browser.wait_element(button_selector, 5)).invoke()

    def close_by_ok(self) -> None:
        selector = ByXPATH("//nx-enable-account-2fa//button[@id='wizardDone']")
        Button(self._browser.wait_element(selector, 5)).invoke()


class DisableTwoFAModal:

    def __init__(self, browser: Browser):
        self._browser = browser

    def submit_totp_code(self, code: str) -> None:
        input_selector = ByXPATH("//nx-2fa-code-input/input")
        InputField(self._browser.wait_element(input_selector, 5)).put(code)
        button_selector = ByXPATH("//nx-disable-account-2fa//button[@type='submit']")
        Button(self._browser.wait_element(button_selector, 5)).invoke()


class RequireCode2FAModal:

    def __init__(self, browser: Browser):
        self._browser = browser

    def submit_totp_code(self, code: str) -> None:
        input_selector = ByXPATH("//nx-2fa-code-input/input")
        InputField(self._browser.wait_element(input_selector, 5)).put(code)
        button_selector = ByXPATH("//nx-require-code-on-login//button[@type='submit']")
        Button(self._browser.wait_element(button_selector, 5)).invoke()


class ToggleSystem2FAModal:

    def __init__(self, browser: Browser):
        self._browser = browser

    def submit_totp_code(self, code: str) -> None:
        input_selector = ByXPATH("//nx-2fa-code-input/input")
        InputField(self._browser.wait_element(input_selector, 5)).put(code)
        button_selector = ByXPATH("//nx-toggle-system-2fa//button[@type='submit']")
        Button(self._browser.wait_element(button_selector, 5)).invoke()
