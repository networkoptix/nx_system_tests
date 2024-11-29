# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui.desktop_ui.media_capturing import ImageCapture
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Checkbox
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QMLComboBoxIncremental
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class FileSettings:

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "type": "nx::vms::client::desktop::MediaFileSettingsDialog",
            "unnamed": 1,
            "visible": 1,
            "occurrence": 1,
            })
        self._hid = hid

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.save_and_close()

    def wait_until_appears(self):
        self._dialog.wait_until_appears()
        return self

    def save_and_close(self):
        _logger.info('%r: Save and close', self)
        ok_button = self._dialog.find_child({
            "text": "OK",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)
        self._dialog.wait_until_closed()

    def _get_enable_dewarping_checkbox(self):
        checkbox = self._dialog.find_child({
            "checkable": True,
            "id": "enableSwitch",
            "text": "Dewarping",
            "type": "SwitchButton",
            "unnamed": 1,
            "visible": True,
            })
        return Checkbox(self._hid, checkbox)

    def enable_dewarping(self):
        _logger.info('%r: Enable dewarping', self)
        self._get_enable_dewarping_checkbox().set(True)

    def disable_dewarping(self):
        _logger.info('%r: Disable dewarping', self)
        self._get_enable_dewarping_checkbox().set(False)

    def _get_dewarping_settings_widget(self):
        return self._dialog.find_child({
            "type": "QQuickWidget",
            "unnamed": 1,
            "visible": 1,
            })

    def set_equirectangular_dewarping_mode(self) -> None:
        _logger.info('%r: Set 360° Equirectangular dewarping mode', self)
        dewarping_mode_box = self._get_dewarping_settings_widget().find_child({
            "id": "typeComboBox",
            "type": "ComboBox",
            "unnamed": 1,
            "visible": True,
            })
        QMLComboBoxIncremental(dewarping_mode_box).select('360° Equirectangular')

    def _get_horizontal_angle_field_by_occurrence(self, occurrence):
        angle_field = self._get_dewarping_settings_widget().find_child({
            "echoMode": 0,
            "id": "textInput",
            "occurrence": occurrence,
            "type": "TextInput",
            "unnamed": 1,
            "visible": True,
            })
        return QLineEdit(self._hid, angle_field)

    def _get_horizontal_alfa_field(self):
        return self._get_horizontal_angle_field_by_occurrence(occurrence=2)

    def _get_horizontal_beta_field(self):
        return self._get_horizontal_angle_field_by_occurrence(occurrence=3)

    def _horizontal_alfa_is_enabled(self) -> bool:
        return self._get_horizontal_alfa_field().is_enabled()

    def _horizontal_beta_is_enabled(self) -> bool:
        return self._get_horizontal_beta_field().is_enabled()

    def are_horizontal_options_accessible(self):
        conditions = (
            self._horizontal_alfa_is_enabled(),
            self._horizontal_beta_is_enabled(),
            )
        return all(conditions)

    def reset_settings(self):
        _logger.info('%r: Reset settings', self)
        reset_button = self._get_dewarping_settings_widget().find_child({
            "checkable": False,
            "id": "resetButton",
            "text": "Reset",
            "type": "TextButton",
            "unnamed": 1,
            "visible": True,
            })
        self._hid.mouse_left_click_on_object(reset_button)
        time.sleep(.5)

    def get_dewarping_preview_equirectangular(self) -> ImageCapture:
        resource_preview = self._get_dewarping_settings_widget().find_child({
            "id": "preview",
            "type": "ResourcePreview",
            "unnamed": 1,
            "visible": True,
            })
        equirectangular_preview = resource_preview.find_child({
            "id": "overlayHolder",
            "type": "Item",
            "unnamed": 1,
            "visible": True,
            })
        return equirectangular_preview.image_capture()

    def get_dewarping_preview_horizon(self) -> ImageCapture:
        return self._get_dewarping_settings_widget().image_capture()

    def get_alfa(self) -> float:
        alfa = self._get_horizontal_alfa_field().get_text().split(' ')[0]
        return float(alfa)

    def set_alfa(self, value: float):
        _logger.info('%r: Set alfa: %s', self, value)
        self._get_horizontal_alfa_field().type_text(str(value))

    def get_beta(self) -> float:
        beta = self._get_horizontal_beta_field().get_text().split(' ')[0]
        return float(beta)

    def set_beta(self, value: float):
        _logger.info('%r: Set betta: %s', self, value)
        self._get_horizontal_beta_field().type_text(str(value))

    def is_dewarping_enabled(self):
        return self._get_enable_dewarping_checkbox().is_checked()
