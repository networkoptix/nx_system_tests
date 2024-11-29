# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import time
from functools import lru_cache

from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.ocr import ImageTextRecognition
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import BaseWindow
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class DisconnectFromCloudDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "type": "nx::vms::client::desktop::OauthLoginDialog",
            "unnamed": 1,
            "visible": 1,
            "windowTitle": "Disconnect System from Nx Cloud",
            })
        self._confirmation = MessageBox(api, hid)

    def _wait_for_text(self, expected_text, timeout: float = 3):
        _logger.info('%r: Wait for text %s. Timeout: %s second(s)', self)
        start_time = time.monotonic()
        while True:
            text_comparer = ImageTextRecognition(self._dialog.image_capture())
            if text_comparer.has_line(expected_text):
                return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError(f"No text {expected_text!r} among recognized text.")
            time.sleep(.1)

    @lru_cache(maxsize=2)
    def _get_field_center(self, field_name: str):
        word_rect = self._get_rectangle(field_name)
        return word_rect.bottom_center().down(30)

    def _get_log_in_button_center(self):
        phrase_rectangle = self._get_rectangle('Log')
        return phrase_rectangle.center()

    def _get_rectangle(self, text: str):
        capture = self._dialog.image_capture()
        text_comparer = ImageTextRecognition(capture)
        word_rect = text_comparer.get_phrase_rectangle(text)
        return word_rect

    def _insert_password(self, password):
        self._hid.mouse_left_click(self._dialog.bounds().top_left().right(250).down(330))
        time.sleep(3)
        self._hid.write_text(password)
        self._hid.mouse_left_click(self._get_field_center('Password'))
        self._hid.write_text(password)

    def _click_login_button(self):
        self._hid.mouse_left_click(self._get_log_in_button_center())

    def disconnect_as_cloud_owner(self):
        _logger.info('%r: Disconnect from Cloud as Cloud owner', self)
        cloud_tab = Widget(self._api, {
            "name": "CloudManagementWidget",
            "type": "QnCloudManagementWidget",
            "visible": 1,
            })
        button_locator = {
            "text": re.compile(r'Continue|Disconnect'),
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            }

        confirmation_button = cloud_tab.find_child(button_locator)
        self._hid.mouse_left_click_on_object(confirmation_button)
        confirmation_button.wait_for_inaccessible()

        self._confirmation.wait_until_appears()
        pattern = re.compile(r"(System|Site) disconnected from Nx Cloud")
        labels = self._confirmation.get_labels()
        if any([pattern.match(label) for label in labels]):
            self._confirmation.close_by_button('OK')
        else:
            raise RuntimeError('Confirmation dialog did not appear')
