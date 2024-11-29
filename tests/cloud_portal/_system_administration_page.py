# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time

from browser.html_elements import Button
from browser.html_elements import InputField
from browser.webdriver import Browser
from browser.webdriver import ByText
from browser.webdriver import ByXPATH
from browser.webdriver import ElementNotFound
from browser.webdriver import Keys
from browser.webdriver import WebDriverElement
from browser.webdriver import get_visible_text
from tests.cloud_portal._translation import TranslationTable
from tests.cloud_portal._translation import en_us
from tests.cloud_portal.elements.nx_checkbox import NxCheckbox


class SystemAdministrationPage:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def wait_for_system_name_field(self, timeout: float = 15) -> None:
        # TODO: Replace this method with get_system_name_field().
        selector = ByXPATH('//nx-text-editable[@id="systemName-editable"]')
        self._browser.wait_element(selector, timeout)

    def wait_for_page_to_be_ready(self, timeout: float = 90) -> None:
        self.wait_for_system_name_field(timeout=timeout)

    def get_merge_with_another_system_button(self) -> '_MergeButton':
        return _MergeButton(
            self._browser.wait_element(
                ByXPATH.quoted("//button[span[text()=%s]]", "Merge with Another System"), 20))

    def get_disconnect_from_cloud_button(self) -> Button:
        return Button(
            self._browser.wait_element(
                ByXPATH('//nx-system-admin-component//nx-process-button//button'), 10))

    def get_disconnect_from_account_button(self) -> Button:
        text = self._translation_table.tr("DISCONNECT_FROM_MY_ACCOUNT")
        return Button(
            self._browser.wait_element(
                ByXPATH.quoted(
                    "//nx-system-admin-component//button[contains(text(),%s)]",
                    text),
                5))

    def get_change_system_name_button(self) -> Button:
        xpath = '//nx-system-admin-component//div[@data-testid="editCameraName"]'
        return Button(self._browser.wait_element(ByXPATH(xpath), 10))

    def get_merge_next_button(self) -> Button:
        return Button(self._browser.wait_element(
            ByXPATH.quoted("//button[contains(text(),%s)]", "Next"), 5))

    def ensure_system_online(self, system_name: str, timeout=10.0) -> None:
        started_at = time.monotonic()
        clicked_next_button = False
        while True:
            try:
                self._browser.wait_element(
                    ByXPATH.quoted(
                        "//nx-modal-merge-content//p[text()=%s]",
                        f"System {system_name} is offline and cannot be merged with the current one",
                        ),
                    3,
                    )
            except ElementNotFound:
                break
            if time.monotonic() - started_at > timeout:
                raise RuntimeError(
                    f"System {system_name} is not ready for merge in {timeout} seconds")
            self.get_merge_next_button().invoke()
            clicked_next_button = True
            time.sleep(0.5)
        if not clicked_next_button:
            self.get_merge_next_button().invoke()

    def primary_first_system(self) -> WebDriverElement:
        return self._browser.wait_element(ByXPATH.quoted("//label[@for=%s]", "firstSystem"), 5)

    def primary_second_system(self) -> WebDriverElement:
        return self._browser.wait_element(ByXPATH.quoted("//label[@for=%s]", "secondSystem"), 5)

    def get_merge_systems_button(self) -> Button:
        return Button(
            self._browser.wait_element(
                ByXPATH.quoted("//button[contains(text(), %s)]", "Merge Systems"), 5))

    def wait_for_systems_merged_success_toast_notification(
            self,
            primary_system_name,
            secondary_system_name,
            ) -> None:
        alert_text = (
            f"Merge of systems {primary_system_name} and {secondary_system_name} completed")
        self._browser.wait_element(ByText(alert_text), 30)

    def get_offline_ribbon(self, timeout: float = 30) -> WebDriverElement:
        text = self._translation_table.tr("SYSTEM_IS_OFFLINE_TEXT")
        selector = ByXPATH.quoted(
            "//nx-ribbon//div[@data-testid='systemMessage' and contains(text(), %s)]",
            text)
        return self._browser.wait_element(selector, timeout)

    def get_owner_text(self) -> str:
        selector = ByXPATH("//nx-system-admin-component//nx-block//span[@class='system-owner']")
        return get_visible_text(self._browser.wait_element(selector, 5))

    def click_change_ownership(self) -> None:
        self._browser.wait_element(ByXPATH('//*[@id="change-ownership"]'), 15).invoke()

    def get_ownership_transfer_text(self) -> str:
        selector = ByXPATH('//nx-system-admin-component//header//span//span')
        return get_visible_text(self._browser.wait_element(selector, 15))

    def accept_ownership_transfer(self) -> None:
        text = self._translation_table.tr("ACCEPT")
        selector = ByXPATH.quoted('//nx-system-admin-component//button[contains(text(), %s)]', text)
        self._browser.wait_element(selector, 5).invoke()

    def get_no_systems_text(self) -> WebDriverElement:
        text = self._translation_table.tr("YOU_HAVE_NO_SYSTEMS_TEXT")
        selector = ByXPATH.quoted("//span[contains(text(), %s)]", text)
        return self._browser.wait_element(selector, 15)

    def _get_mandatory_2fa_checkbox(self) -> NxCheckbox:
        return NxCheckbox(self._browser, ByXPATH("//nx-checkbox[@name='mandatory2fa']"))

    def turn_on_mandatory_2fa(self) -> None:
        self._get_mandatory_2fa_checkbox().check()

    def turn_off_mandatory_2fa(self) -> None:
        self._get_mandatory_2fa_checkbox().uncheck()


class _MergeButton:

    def __init__(self, webdriver_element: WebDriverElement):
        self._button = Button(webdriver_element)

    def wait_until_clickable(self) -> None:
        timeout_sec = 5
        started_at = time.monotonic()
        while True:
            if self._button.is_active():
                return
            if time.monotonic() - started_at > timeout_sec:
                raise RuntimeError(
                    f"Element is not enabled within timeout of {timeout_sec} seconds")
            time.sleep(0.5)

    def invoke(self) -> None:
        self.wait_until_clickable()
        self._button.invoke()

    def is_active(self) -> bool:
        return self._button.is_active()


class DisconnectFromCloudModal:

    def __init__(self, browser: Browser):
        self._browser = browser
        self._selector = '//nx-modal-disconnect-content/form'

    def _get_element(self) -> WebDriverElement:
        return self._browser.wait_element(ByXPATH(self._selector), 10)

    def get_close_button(self) -> Button:
        element = self._get_element()
        return Button(ByXPATH(".//button[contains(@class, 'close')]").find_in(element))

    def get_cancel_button(self) -> Button:
        element = self._get_element()
        return Button(ByXPATH('.//nx-cancel-button/button').find_in(element))

    def get_disconnect_system_button(self) -> Button:
        element = self._get_element()
        selector = ".//nx-process-button[@data-testid='disconnectSystemBtn']//button"
        return Button(ByXPATH(selector).find_in(element))


class DisconnectFromAccountModal:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def get_warning_text(self) -> str:
        text = self._translation_table.tr('DISCONNECT_MODAL_WARNING')
        selector = ByXPATH.quoted("//nx-modal-generic-content//p[contains(text(), %s)]", text)
        return get_visible_text(self._browser.wait_element(selector, 5))

    def get_disconnect_button(self) -> Button:
        text = self._translation_table.tr("DISCONNECT")
        return Button(
            self._browser.wait_element(
                ByXPATH.quoted(
                    "//nx-modal-generic-content//button[contains(text(), %s)]",
                    text),
                5))

    def get_cancel_button(self) -> Button:
        text = self._translation_table.tr("CANCEL_2")
        return Button(
            self._browser.wait_element(
                ByXPATH.quoted(
                    "//nx-modal-generic-content//button[contains(., %s)]",
                    text),
                5))


class DisconnectedFromCloudToast:

    def __init__(self, browser: Browser, translation_table: TranslationTable, cloud_name: str):
        self._browser = browser
        text = translation_table.tr('SYSTEM_DISCONNECTED_TOAST_TEXT')
        text = text.replace("%CLOUD_NAME%", cloud_name)
        self._element = ByXPATH.quoted(
            "//nx-toast//div[@class='alert alert-success toast']/span[contains(text(),%s)]", text)

    def _is_visible(self) -> bool:
        try:
            self._browser.wait_element(self._element, 0)
        except ElementNotFound:
            return False
        return True

    def wait_until_shown(self, timeout: float) -> None:
        started_at = time.monotonic()
        while True:
            if self._is_visible():
                return
            if started_at + timeout < time.monotonic():
                raise TimeoutError(f"{self.__class__.__name__} not shown after {timeout}s")
            time.sleep(0.5)

    def wait_until_not_shown(self, timeout: float) -> None:
        started_at = time.monotonic()
        while True:
            if not self._is_visible():
                return
            if started_at + timeout < time.monotonic():
                raise TimeoutError(f"{self.__class__.__name__} still shown after {timeout}s")
            time.sleep(0.5)


class TransferOwnershipModal:

    def __init__(self, browser: Browser, translation_table: TranslationTable = en_us):
        self._browser = browser
        self._translation_table = translation_table

    def _get_action_button(self) -> Button:
        # Blue button that initiates proceeding to the next step of ownership transfer.
        selector = ByXPATH('//nx-modal-transfer-ownership-content//nx-async-action-button//button')
        return Button(self._browser.wait_element(selector, 5))

    def _get_email_field(self) -> InputField:
        selector = ByXPATH("//nx-transfer-stepper//nx-autocomplete/input")
        return InputField(self._browser.wait_element(selector, 5))

    def input_email_of_new_owner(self, email: str):
        self._get_email_field().put(email)
        # Hitting Enter is necessary or input will fail.
        self._browser.request_keyboard().send_keys(Keys.ENTER)

    def click_next(self) -> None:
        self._get_action_button().invoke()

    def get_confirmation_text(self) -> str:
        text = self._translation_table.tr("OWNERSHIP_TRANSFER_START")
        selector = ByXPATH.quoted('//nx-transfer-stepper//p[contains(., %s)]', text)
        return get_visible_text(self._browser.wait_element(selector, 15))

    def get_warning_text(self) -> str:
        text = self._translation_table.tr("OWNERSHIP_TRANSFER_WARNING")
        selector = ByXPATH.quoted('//nx-transfer-stepper[contains(., %s)]', text)
        return get_visible_text(self._browser.wait_element(selector, 5))

    def click_transfer(self) -> None:
        self._get_action_button().invoke()

    def wait_for_request_has_been_sent_text(self) -> None:
        text = self._translation_table.tr("REQUEST_SENT")
        self._browser.wait_element(ByText(text), 5)

    def close_by_ok(self) -> None:
        selector = ByXPATH('//nx-transfer-stepper//button')
        self._browser.wait_element(selector, 5).invoke()
