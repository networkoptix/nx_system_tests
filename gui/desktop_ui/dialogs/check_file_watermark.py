# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui.desktop_ui.wrappers import BaseWindow
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class CheckFileWatermarkDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "SignDialog",
            "type": "SignDialog",
            "visible": 1,
            "occurrence": 1,
            })
        self._hid = hid

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.close()

    def wait_for_accessible(self):
        self._dialog.wait_for_accessible()

    def close(self):
        _logger.info('%r: Close Check File Watermark Dialog', self)
        ok_button = self._dialog.find_child({
            "text": "OK",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)
        self._dialog.wait_until_closed()

    def _get_matching_state(self):
        return self._dialog.find_child({
            "name": "signInfoLabel",
            "type": "QnSignInfo",
            "visible": 1,
            })

    def wait_for_matched(self, timeout: float = 5):
        _logger.info('%r: Wait for watermarks matched. Timeout: %s second(s)', self, timeout)
        started_at = time.monotonic()
        while True:
            if self._get_matching_state().wait_property('signIsMatched'):
                return
            if time.monotonic() - started_at > timeout:
                raise RuntimeError("Watermark is not matched")
            time.sleep(0.5)

    def wait_for_not_matched(self, timeout: float = 5):
        _logger.info('%r: Wait for watermarks not matched. Timeout: %s second(s)', self, timeout)
        started_at = time.monotonic()
        while True:
            if not self._get_matching_state().wait_property('signIsMatched'):
                return
            if time.monotonic() - started_at > timeout:
                raise RuntimeError("Watermark is matched")
            time.sleep(0.5)
