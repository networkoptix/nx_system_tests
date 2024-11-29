# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from browser.html_elements import Button
from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import ByCSS
from browser.webdriver import ByXPATH
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us
from tests.cloud_portal.elements.nx_checkbox import NxCheckbox


class RegisterPage:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def _get_email_field(self) -> InputField:
        return InputField(self._browser.wait_element(ByCSS("#email"), 15))

    def _get_first_name_field(self) -> InputField:
        return InputField(self._browser.wait_element(ByCSS("#firstName"), 15))

    def _get_last_name_field(self) -> InputField:
        return InputField(self._browser.wait_element(ByCSS("#lastName"), 15))

    def _get_password_field(self) -> InputField:
        return InputField(self._browser.wait_element(ByCSS("#createAccountPassword"), 15))

    def _get_terms_and_conditions_checkbox(self) -> NxCheckbox:
        return NxCheckbox(self._browser, ByXPATH("//nx-checkbox[@name='termsAndConditions']"))

    def _create_account(self) -> None:
        create_account_text = self._translation_table.tr("CREATE_ACCOUNT_BUTTON_TEXT")
        selector = ByXPATH.quoted(
            "//nx-authorize-create-account-component//button[contains(text(), %s)]",
            create_account_text,
            )
        create_account_button = Button(self._browser.wait_element(selector, 5))
        create_account_button.invoke()

    def register(self, first_name: str, last_name: str, password: str) -> None:
        self._get_first_name_field().put(first_name)
        self._get_last_name_field().put(last_name)
        self._get_password_field().put(password)
        self._get_terms_and_conditions_checkbox().check()
        self._create_account()

    def register_with_email(self, email: str, first_name: str, last_name: str, password: str) -> None:
        self._get_email_field().put(email)
        self._get_first_name_field().put(first_name)
        self._get_last_name_field().put(last_name)
        self._get_password_field().put(password)
        self._get_terms_and_conditions_checkbox().check()
        self._create_account()

    def get_locked_email_field(self) -> InputField:
        return InputField(self._browser.wait_element(
            ByXPATH("//nx-authorize-create-account-component//input[@name='registerEmailLocked']"),
            15,
            ))
