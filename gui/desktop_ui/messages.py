# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui import testkit
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import Checkbox
from gui.desktop_ui.wrappers import QLabel
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QTreeView
from gui.testkit import ObjectNotFound
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class MessageBoxContentException(Exception):
    pass


class MessageBox(BaseWindow):
    # Simple message box appearing with error or notification message.

    def __init__(self, api: TestKit, hid: HID):
        super().__init__(api=api, locator_or_obj={
            "name": "MessageBox",
            "type": "QnMessageBox",
            "visible": 1,
            })
        self._hid = hid

    def get_button_with_text(self, button_text):
        # There is a Client bug with duplicate buttons. It occurs rarely, and probably it is a Qt bug.
        # Once it is fixed, it will be necessary to replace find_children() with find_child().
        # See: https://networkoptix.atlassian.net/browse/VMS-47626
        buttons = self.find_children({
            "type": "QPushButton",
            'text': button_text,
            "unnamed": 1,
            "visible": 1,
            })
        if len(buttons) > 1:
            _logger.warning("Buttons with the text '%s' were found: %i", button_text, len(buttons))
        return Button(buttons[0])

    def get_title(self) -> str:
        main_label = self.find_child({
            "name": "mainLabel",
            "type": "QLabel",
            "visible": 1,
            })
        return QLabel(main_label).get_text()

    def has_label(self, expected_text):
        _logger.info('%r: Looking for label with text: %s', self, expected_text)
        for label in self.get_labels():
            if label == expected_text:
                return True
            _logger.debug("Current label: %s", label)
        return False

    def has_text(self, expected_text: str) -> bool:
        _logger.info('%r: Looking for text: %s', self, expected_text)
        for value in [self.get_title(), *self.get_labels(), *self.get_info()]:
            if expected_text in value:
                return True
            _logger.debug("Current text: %s", value)
        return False

    def wait_until_has_label(self, expected_text, timeout: float = 20):
        _logger.info(
            '%r: Wait for label: %s. Timeout: %s second(s)',
            self, expected_text, timeout)
        self.wait_until_appears(timeout)
        start = time.monotonic()
        while True:
            if self.has_label(expected_text):
                return self
            if time.monotonic() - start > timeout:
                raise RuntimeError(f"Timed out. Message box doesn't have label {expected_text}")
            time.sleep(1)

    def close_using_event(self):
        _logger.info('%r: Close by event', self)
        self.close()

    def click_button_with_text(self, button_text):
        _logger.info('%r: Click button: %s', self, button_text)
        self.wait_until_appears()
        button = self.get_button_with_text(button_text)
        self._hid.mouse_left_click_on_object(button)

    def close_by_button(self, button_text, wait_close: bool = True):
        _logger.info('%r: Close by button: %s', self, button_text)
        self.wait_until_appears()
        try:
            _logger.debug('Text from message box: %s', self.get_title())
        except testkit.ObjectAttributeNotFound:
            _logger.debug("Can't get text from the message box")
        button = self.get_button_with_text(button_text)
        self._hid.mouse_left_click_on_object(button)
        if wait_close:
            self.wait_until_closed()

    def set_dont_show_again(self, value: bool):
        _logger.info('%r: Set dont show again checkbox value to %s', self, value)
        checkbox = self.find_child({
            "name": "checkBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        Checkbox(self._hid, checkbox).set(value)

    def get_labels(self):
        items = []
        try:
            self.wait_for_object()
            objects = self.find_children({
                "type": "QLabel",
                "visible": 1,
                })
        except ObjectNotFound:
            return items
        for item in objects:
            if not item.is_accessible_timeout(0.5):
                continue
            text = item.get_text()
            if text != '':
                items.append(text)
        return items

    def get_info(self) -> list:
        items = []
        objects = self.find_children({
            'type': 'nx::vms::client::desktop::TreeView',
            'visible': 1,
            })
        for item in objects:
            items.extend(QTreeView(item).item_names())
        return items


class InputPasswordDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._form = BaseWindow(api=api, locator_or_obj={
            "name": "InputDialog",
            "type": "QnInputDialog",
            "visible": 1,
            })
        self._hid = hid

    def get_label(self):
        label = self._form.find_child({
            "name": "captionLabel",
            "type": "QLabel",
            "visible": 1,
            })
        return QLabel(label).get_text()

    def get_error_message(self) -> str:
        label = self._form.find_child({
            "type": "QLabel",
            "unnamed": 1,
            "visible": 1,
            })
        return label.get_text()

    def is_shown(self):
        return self._form.is_accessible()

    def wait_until_closed(self):
        self._form.wait_until_closed()

    def click_ok(self):
        _logger.info('%r: Click OK button', self)
        ok_button = self._form.find_child({
            "text": "OK",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)

    def click_cancel(self):
        _logger.info('%r: Click Cancel button', self)
        cancel_button = self._form.find_child({
            "text": "Cancel",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(cancel_button)

    def _get_insert_password_field(self):
        field = self._form.find_child({
            "name": "passwordLineEdit_passwordLineEdit",
            "type": "QLineEdit",
            "visible": 1,
            })
        return QLineEdit(self._hid, field)

    def read_password(self):
        return self._get_insert_password_field().get_text()

    def input_password(self, password):
        _logger.info('%r: Input password: %s', self, password)
        self._get_insert_password_field().type_text(password)

    def _get_eye_icon(self):
        icon = self._form.find_child({
            "type": "nx::vms::client::desktop::PasswordPreviewButton",
            "unnamed": 1,
            "visible": 1,
            })
        return Checkbox(self._hid, icon)

    def show_password(self):
        _logger.info('%r: Show password', self)
        self._get_eye_icon().set(True)

    def hide_password(self):
        _logger.info('%r: Hide password', self)
        self._get_eye_icon().set(False)


class ProgressDialog:

    def __init__(self, api: TestKit):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "type": "nx::vms::client::desktop::ProgressDialog",
            "unnamed": 1,
            "visible": 1,
            "occurrence": 1,
            })

    def wait_until_closed(self, timeout: float = 25):
        _logger.info('%r: Wait until closed. Timeout: %s second(s)', self, timeout)
        if self._dialog.is_accessible_timeout(2):
            self._dialog.wait_until_closed(timeout)

    def wait_until_open(self, timeout: float = 60):
        _logger.info('%r: Wait until open. Timeout: %s second(s)', self, timeout)
        self._dialog.wait_for_accessible(timeout)

    def is_open(self):
        return self._dialog.is_accessible_timeout(0.2)


class AboutDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "AboutDialog",
            "type": "QnAboutDialog",
            "visible": 1,
            })
        self._hid = hid

    @staticmethod
    def open_by_f1(api: TestKit, hid: HID) -> 'AboutDialog':
        _logger.info('AboutDialog: Open by hot key')
        hid.keyboard_hotkeys('F1')
        dialog = AboutDialog(api, hid)
        dialog._dialog.wait_for_accessible()
        return dialog

    def close(self):
        _logger.info('%r: Save and close', self)
        close_button = self._dialog.find_child({
            "text": "Close",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(close_button)
        self._dialog.wait_until_closed()

    def _get_support_info(self):
        support_information_block = self._dialog.find_child({
            "name": "supportGroupBox",
            "type": "QGroupBox",
            "visible": 1,
            })
        return [i.get_text() for i in support_information_block.find_children({
            "type": "QLabel",
            "visible": 1,
            })]

    def has_support_text(self, text):
        for field in self._get_support_info():
            if text in field:
                return True
        return False

    def has_license_and_support_field(self):
        support_info = self._get_support_info()
        return 'Regional / License support' in support_info and len(support_info) > 2


class WebPageCertificateDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._dialog = BaseWindow(self._api, locator_or_obj={
            'name': 'MessageBox',
            'type': 'nx::vms::client::desktop::WebPageCertificateDialog',
            'visible': 1,
            })

    def connect_anyway(self):
        button = self._dialog.find_child({'text': 'Connect anyway', 'type': 'QPushButton'})
        self._hid.mouse_left_click_on_object(Button(button))

    def is_accessible_timeout(self, timeout: float) -> bool:
        return self._dialog.is_accessible_timeout(timeout=timeout)
