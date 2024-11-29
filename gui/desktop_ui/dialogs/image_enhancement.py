# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Checkbox
from gui.desktop_ui.wrappers import QSpinBox
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class ImageEnhancementDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "AdjustVideoDialog",
            "type": "QnAdjustVideoDialog",
            "visible": 1,
            })
        self._hid = hid

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.save()

    def _get_image_enhancement_checkbox(self):
        checkbox = self._dialog.find_child({
            "name": "enableAdjustment",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, checkbox)

    def get_image_enhancement(self) -> bool:
        return self._get_image_enhancement_checkbox().is_checked()

    def set_image_enhancement(self, value: bool):
        _logger.info('%r: Set image enhancement checkbox value to %s', self, value)
        self._get_image_enhancement_checkbox().set(value)

    def set_gamma(self, value: [int, str, float]):
        _logger.info('%r: Set gamma value to %s', self, value)
        gamma_spinbox = self._dialog.find_child({
            "name": "gammaSpinBox",
            "type": "QDoubleSpinBox",
            "visible": 1,
            })
        QSpinBox(self._hid, gamma_spinbox).type_text(str(value))

    def set_black_level(self, value: [int, str, float]):
        _logger.info('%r: Set black level value to %s', self, value)
        black_level_spin_box = self._dialog.find_child({
            "name": "blackLevelsSpinBox",
            "type": "QDoubleSpinBox",
            "visible": 1,
            })
        QSpinBox(self._hid, black_level_spin_box).type_text(str(value))

    def set_white_level(self, value: [int, str, float]):
        _logger.info('%r: Set white level value to %s', self, value)
        white_level_spin_box = self._dialog.find_child({
            "name": "whiteLevelsSpinBox",
            "type": "QDoubleSpinBox",
            "visible": 1,
            })
        QSpinBox(self._hid, white_level_spin_box).type_text(str(value))

    def save(self):
        _logger.info('%r: Save and close', self)
        ok_button = self._dialog.find_child({
            "text": "OK",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)
        self._dialog.wait_until_closed()

    def close(self):
        self._dialog.close()

    def wait_until_appears(self) -> 'ImageEnhancementDialog':
        self._dialog.wait_until_appears()
        return self

    def wait_until_closed(self):
        self._dialog.wait_until_closed()
