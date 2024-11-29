# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import re

from browser.html_elements import Button
from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import ByCSS
from browser.webdriver import ByXPATH
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us


class LoginComponent:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def get_email_field(self) -> InputField:
        return InputField(self._browser.wait_element(ByCSS("#authorizeEmail"), 15))

    def get_wrong_backup_code_error(self) -> WebDriverElement:
        text = self._translation_table.tr("WRONG_BACKUP_CODE")
        selector = ByXPATH.quoted("//p[contains(text(), %s)]", text)
        return self._browser.wait_element(selector, timeout=5.0)

    def get_next_button(self) -> Button:
        selector = ByXPATH.quoted(
            "//nx-authorize-component//nx-process-button//button[contains(text(), %s)]",
            self._translation_table.tr("NEXT"),
            )
        return Button(self._browser.wait_element(selector, 5))

    def _get_password_field(self) -> InputField:
        return InputField(self._browser.wait_element(ByCSS("#authorizePassword"), 5))

    def _get_log_in_button(self) -> Button:
        selector = ByXPATH.quoted(
            "//nx-authorize-component//nx-process-button//button[contains(text(), %s)]",
            self._translation_table.tr("LOG_IN"),
            )
        return Button(self._browser.wait_element(selector, 5))

    def login(self, username: str, password: str) -> None:
        self.get_email_field().put(username)
        self.get_next_button().invoke()
        password_field = self._get_password_field()
        password_field.put(password)
        login_button = self._get_log_in_button()
        login_button.invoke()

    def login_with_password_only(self, password: str) -> None:
        password_field = self._get_password_field()
        password_field.put(password)
        login_button = self._get_log_in_button()
        login_button.invoke()

    def submit_totp_code(self, code: str) -> None:
        field = InputField(self._browser.wait_element(ByXPATH("//*[@id='authCode']"), 5))
        field.put(code)
        self._get_log_in_button().invoke()

    def submit_backup_code(self, code: str) -> None:
        field = InputField(self._browser.wait_element(ByXPATH("//input[@id='backupCode']"), timeout=5.0))
        field.clear()
        field.put(code)
        self._get_log_in_button().invoke()

    def get_forgot_password_button(self) -> Button:
        selector = ByXPATH.quoted(
            "//nx-authorize-component//button/span[contains(text(), %s)]",
            self._translation_table.tr("FORGOT_PASSWORD"),
            )
        return Button(self._browser.wait_element(selector, 5))

    def get_backup_code_button(self) -> Button:
        selector = ByXPATH.quoted(
            "//nx-authorize-component//button[contains(., %s)]",
            self._translation_table.tr("NO_ACCESS_TO_AUTH_APP"),
            )
        return Button(self._browser.wait_element(selector, 5))

    def get_accept_risk_link(self) -> WebDriverElement:
        text = self._translation_table.tr("ACCEPT_RISK_TEXT")
        xpath = "//nx-authorize-not-secure-component//button/span[contains(text(), %s)]"
        return self._browser.wait_element(ByXPATH.quoted(xpath, text), 10)


class ResetPasswordComponent:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def get_email_field(self) -> InputField:
        return InputField(self._browser.wait_element(ByCSS("#resetPasswordEmail"), 15))

    def get_reset_password_button(self) -> Button:
        text = self._translation_table.tr("RESET_PASSWORD")
        selector = ByXPATH.quoted("//nx-process-button//button[contains(text(), %s)]", text)
        return Button(self._browser.wait_element(selector, 5))


class ConnectSystemToCloudComponent:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def get_connect_system_label(self) -> WebDriverElement:
        text = self._translation_table.tr("CONNECT_SYSTEM_TO")
        selector = ByXPATH.quoted("//nx-bind-system-to-cloud//h3[contains(text(), %s)]", text)
        return self._browser.wait_element(selector, 10)

    def get_user_email(self) -> str:
        xpath = "//nx-bind-system-to-cloud/main/div"
        all_text = get_visible_text(self._browser.wait_element(ByXPATH(xpath), 5))
        [email] = re.findall(r'\n(\w+\+\d+\@\w+\.\w+)', all_text)
        return email

    def connect(self) -> None:
        text = self._translation_table.tr("CONNECT")
        selector = ByXPATH.quoted("//nx-bind-system-to-cloud//button[contains(text(), %s)]", text)
        Button(self._browser.wait_element(selector, 10)).invoke()
