# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import time

from gui.desktop_ui.ocr import ImageTextRecognition
from gui.desktop_ui.ocr import TextNotFound
from gui.desktop_ui.screen import ScreenRectangle
from gui.desktop_ui.wrappers import BaseWindow
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class SystemSetupDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "type": "nx::vms::client::desktop::SetupWizardDialog",
            "unnamed": 1,
            "visible": 1,
            })

    def setup(self, title, password):
        _logger.info('%r: Start setup system', self)
        self._dialog.wait_for_accessible(15)
        self._wait_for_text('Get Started with Nx Witness', 20)
        self._click_button_by_text_pattern(re.compile('Setup New (System|Site)', re.IGNORECASE))
        self._wait_for_text_with_pattern(re.compile('Enter (System|Site) Name', re.IGNORECASE))
        self._set_system_name(title)
        self._click_button_with_text('Next')
        self._wait_for_text('Set up an administrator')
        self._setup_password(password)
        self._confirm_password(password)
        self._click_button_with_text('Next')
        self._wait_for_text_with_pattern(
            re.compile('(System|Site) is ready for use', re.IGNORECASE),
            )
        self._click_button_with_text('Finish')

    def _wait_for_text(self, text: str, timeout: float = 10):
        start = time.monotonic()
        while True:
            text_comparer = ImageTextRecognition(self._dialog.image_capture())
            try:
                index = text_comparer.line_index(text)
                return index, text_comparer
            except TextNotFound:
                _logger.info('Text not found yet')
            if time.monotonic() - start > timeout:
                raise RuntimeError(f"No text {text!r} among recognized text.")
            time.sleep(.5)

    def _wait_for_text_with_pattern(self, pattern: re.Pattern):
        started_at = time.monotonic()
        while True:
            text_comparer = ImageTextRecognition(self._dialog.image_capture())
            try:
                index = text_comparer.line_index_by_pattern(pattern)
                return index, text_comparer
            except TextNotFound:
                _logger.info('Text not found yet')
            if time.monotonic() - started_at > 10:
                raise RuntimeError(f"No text matches {pattern!r} among recognized text")
            time.sleep(.5)

    def _get_text_rectangle(self, button_text: str) -> ScreenRectangle:
        index, text_comparer = self._wait_for_text(button_text)
        return text_comparer.get_rectangle_by_index(index)

    def _get_text_rectangle_by_text_pattern(self, text_pattern: re.Pattern) -> ScreenRectangle:
        index, text_comparer = self._wait_for_text_with_pattern(text_pattern)
        return text_comparer.get_rectangle_by_index(index)

    def _click_button_with_text(self, text):
        rect = self._get_text_rectangle(text)
        self._hid.mouse_left_click(rect.center())

    def _click_button_by_text_pattern(self, pattern: re.Pattern):
        rect = self._get_text_rectangle_by_text_pattern(pattern)
        self._hid.mouse_left_click(rect.center())

    def _set_system_name(self, name: str):
        _logger.info('%r: Set system name to %s', self, name)
        self._hid.mouse_left_click_on_object(self._dialog)
        self._hid.keyboard_hotkeys('Ctrl', 'A')
        self._hid.write_text(name)

    def _setup_password(self, password: str):
        _logger.info('Setup system password')
        # Sometimes it is Password from the confirmation field caught.
        # In this case the click will go wrong. Now the easiest way is to find the only
        # Repeat word and make a small shift up from the confirmation field
        # to click on the correct one.
        rect_confirm = self._get_text_rectangle('Repeat')
        rect_center = rect_confirm.top_center().up(50)
        self._hid.mouse_left_click(rect_center)
        self._hid.write_text(password)

    def _confirm_password(self, password: str):
        _logger.info('Confirm system password')
        rect = self._get_text_rectangle('Repeat')
        self._hid.mouse_left_click(rect.center())
        self._hid.write_text(password)

    def wait_for_accessible(self):
        self._dialog.wait_for_accessible()
