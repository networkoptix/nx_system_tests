# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.webdriver import Browser
from browser.webdriver import ByText
from browser.webdriver import ByXPATH
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us


class AccountCreatedConfirmation:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def wait_for_account_created_text(self):
        selector = ByXPATH.quoted(
            "//nx-authorize-component//nx-authorize-activate-account-component//h3[contains(text(), %s)]",
            self._translation_table.tr("ACCOUNT_CREATED"),
            )
        self._browser.wait_element(selector, 5)


class AccountActivatedConfirmation:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def wait_for_account_activated_text(self) -> None:
        text = self._translation_table.tr("ACCOUNT_ACTIVATED")
        self._browser.wait_element(ByText(text), 5)

    def log_in(self) -> None:
        log_in_button = self._browser.wait_element(
            ByXPATH("//nx-authorize-activate-account-component//nx-process-button//button"),
            5,
            )
        log_in_button.invoke()


class PasswordSetConfirmation:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def wait_for_set_new_password_text(self) -> None:
        text = self._translation_table.tr("SET_NEW_PASSWORD")
        self._browser.wait_element(ByText(text), 5)

    def wait_for_password_is_set_text(self) -> None:
        text = self._translation_table.tr("PASSWORD_IS_SET")
        self._browser.wait_element(ByText(text), 5)

    def open_login_page(self) -> None:
        selector = ByXPATH("//nx-authorize-reset-password-component//nx-process-button//button")
        log_in_button = self._browser.wait_element(selector, 5)
        log_in_button.invoke()
