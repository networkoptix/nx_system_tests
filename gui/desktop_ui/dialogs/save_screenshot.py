# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import ComboBox
from gui.desktop_ui.wrappers import QLineEdit
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class SaveScreenshotDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "QFileDialog",
            "type": "QnCustomFileDialog",
            "visible": 1,
            })
        self._file_type_box_locator = {
            "name": "fileTypeCombo",
            "type": "QComboBox",
            "visible": 1,
            }

    def _get_timestamp_combo_box(self):
        _timestamp_label_locator = {
            "text": "Timestamp:",
            "type": "QLabel",
            "unnamed": 1,
            "visible": 1,
            }
        timestamp_combo_box = self._dialog.find_child({
            "aboveWidget": self._file_type_box_locator,
            "leftWidget": _timestamp_label_locator,
            "type": "QComboBox",
            "unnamed": 1,
            "visible": 1,
            })
        return ComboBox(self._hid, timestamp_combo_box)

    def _get_camera_name_combo_box(self):
        _camera_name_locator = {
            "text": "Camera name:",
            "type": "QLabel",
            "unnamed": 1,
            "visible": 1,
            }
        camera_name_combo_box = self._dialog.find_child({
            "leftWidget": _camera_name_locator,
            "type": "QComboBox",
            "unnamed": 1,
            "visible": 1,
            })
        return ComboBox(self._hid, camera_name_combo_box)

    def _get_filetype_combo_box(self):
        filetype_combo_box = self._dialog.find_child(self._file_type_box_locator)
        return ComboBox(self._hid, filetype_combo_box)

    def wait_until_appears(self) -> 'SaveScreenshotDialog':
        self._dialog.wait_until_appears()
        return self

    def make_screenshot(self, file_name, file_type, timestamp=None, camera_name=None):
        _logger.info(
            '%r: Save screenshot with path %s, file type %s',
            self, file_name, file_type)
        file_name_field = self._dialog.find_child({
            "name": "fileNameEdit",
            "type": "QLineEdit",
            "visible": 1,
            })
        QLineEdit(self._hid, file_name_field).set_text_without_validation(str(file_name))
        self._get_filetype_combo_box().select(file_type)
        if timestamp is not None:
            self._get_timestamp_combo_box().select(timestamp)
        if camera_name is not None:
            self._get_camera_name_combo_box().select(camera_name)
        save_button = self._dialog.find_child({
            "text": "Save",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(save_button)
        self._dialog.wait_until_closed()

        msg_box = MessageBox(self._api, self._hid)
        if msg_box.is_accessible_timeout(.5):
            overwrite_button = msg_box.get_button_with_text("Overwrite")
            self._hid.mouse_left_click_on_object(overwrite_button)
        time.sleep(.5)
