# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from functools import lru_cache
from typing import Collection
from typing import Mapping
from typing import Optional
from typing import Sequence

from gui.desktop_ui.dialogs.camera_settings import CameraSettingsDialog
from gui.desktop_ui.ocr import ImageTextRecognition
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QSpinBox
from gui.desktop_ui.wrappers import TextField
from gui.testkit import ObjectNotFound
from gui.testkit import TestKit
from gui.testkit.hid import HID


class ActiveSettingsSection:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid

    @lru_cache
    def _get_base_dialog(self):
        return CameraSettingsDialog(self._api, self._hid)

    def open(self):
        tab = self._get_base_dialog().plugins_tab
        tab.open_device_agent_settings('Active settings section')

    def click_active_checkbox(self):
        checkbox = self._get_base_dialog().find_child({
            "type": "CheckBox",
            "visible": 1,
            "id": "checkBox",
            "text": "Active CheckBox",
            })
        self._hid.mouse_left_click(checkbox.center())

    def get_active_combobox_with_label_text(self, label_text: str) -> '_ActiveComboBox':
        combobox = self._get_base_dialog().find_child({
            "visible": True,
            "type": "ComboBox",
            'labelText': label_text,
            'id': 'control',
            })
        inner_box = combobox.find_child({"type": "ComboBox"})
        return _ActiveComboBox(self._hid, inner_box)

    def has_combobox_within_timeout(self, label_text: str, timeout: float = 2) -> bool:
        started_at = time.monotonic()
        while True:
            try:
                self.get_active_combobox_with_label_text(label_text)
                return True
            except ObjectNotFound:
                _logger.info("Combobox %s has not been seen yet", label_text)
            if time.monotonic() - started_at > timeout:
                return False
            time.sleep(0.1)

    def get_radiobutton_collection(self) -> '_RadiobuttonCollection':
        button_objects = self._get_base_dialog().find_children({
            "type": "RadioButton",
            "visible": True,
            })
        return _RadiobuttonCollection(button_objects)

    def get_active_maximum_spinbox(self) -> '_ActiveSpinBox':
        spinbox = self._get_base_dialog().find_child({
            "type": "SpinBox",
            "visible": True,
            "id": "control",
            "labelText": "Active Maximum",
            })
        return _ActiveSpinBox(self._hid, spinbox)

    def get_active_minimum_spinbox(self) -> '_ActiveSpinBox':
        spinbox = self._get_base_dialog().find_child({
            "type": "SpinBox",
            "visible": True,
            "id": "control",
            "labelText": "Active Minimum",
            })
        return _ActiveSpinBox(self._hid, spinbox)

    def get_show_message_button(self) -> Button:
        button = self._get_base_dialog().find_child({
            "type": "Button",
            "visible": True,
            "text": "Show Message...",
            })
        return Button(button)

    def get_field(self) -> TextField:
        field = self._get_base_dialog().find_child({
            "visible": True,
            "type": "TextField",
            "id": "textField",
            })
        return TextField(self._hid, field)

    def get_show_webpage_button(self) -> Button:
        button = self._get_base_dialog().find_child({
            "type": "Button",
            "visible": True,
            "text": "Show Webpage...",
            })
        return Button(button)


class _RadiobuttonCollection:

    def __init__(self, elements: Sequence[Widget]):
        buttons = {}
        for button in elements:
            buttons[button.wait_property('text')] = Button(button)
        self._name_to_button = buttons

    def get_button(self, name: str) -> Optional[Button]:
        return self._name_to_button.get(name)

    def get_sorted_names(self) -> Collection[str]:
        return sorted(self._name_to_button.keys())


class ActiveSettingsDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._dialog = BaseWindow(
            self._api,
            {
                "type": "SettingsDialog",
                "id": "dialog",
                "visible": True,
                },
            )

    def wait_for_accessible(self):
        self._dialog.wait_for_accessible()

    def get_text_field(self) -> TextField:
        return TextField(
            self._hid,
            self._dialog.find_child({
                "visible": True,
                "type": "TextField",
                "id": "textField",
                }))

    def close_by_ok(self):
        ok_button = self._dialog.find_child({
            "type": "Button",
            "text": "OK",
            })
        self._hid.mouse_left_click(ok_button.center())
        self._dialog.wait_until_closed()

    def wait_for_inaccessible(self):
        self._dialog.wait_for_inaccessible()


class _ActiveSpinBox(QSpinBox):

    def _get_field(self):
        field = self._widget.find_child({"type": "QQuickPre64TextInput"})
        return QLineEdit(self._hid, field)

    def _get_arrows(self) -> Mapping[str, Widget]:
        [up, down] = self._widget.find_children({
            "type": "ArrowIcon",
            "visible": True,
            })
        return {"Up": up, "Down": down}

    def get_text(self):
        return self._get_field().get_text()

    def type_text(self, text: str, need_activate: bool = True):
        self._get_field().type_text(text, need_activate)

    def up_arrow(self) -> Widget:
        return self._get_arrows()["Up"]

    def down_arrow(self) -> Widget:
        return self._get_arrows()["Down"]

    def spin_up(self):
        self._hid.mouse_left_click(self.up_arrow().center())

    def spin_down(self):
        self._hid.mouse_left_click(self.down_arrow().center())


class WebDialog:

    def __init__(self, api: TestKit):
        self._dialog = BaseWindow(
            api,
            {"type": "nx::vms::client::desktop::WebViewDialog", "visible": True},
            )

    def has_phrase(self, expected_text) -> bool:
        text_comparer = ImageTextRecognition(self._dialog.image_capture())
        return text_comparer.has_line(expected_text)

    def wait_for_phrase_exists(self, expected_text, timeout=20):
        _logger.info(
            '%r: Wait for text: %s. Timeout: %s second(s)',
            self, expected_text, timeout)
        start_time = time.monotonic()
        while True:
            if self.has_phrase(expected_text):
                return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError(f"No text {expected_text} found")
            time.sleep(.5)

    def get_ok_button(self) -> Button:
        button = self._dialog.find_child({
            "text": "OK",
            "type": "QPushButton",
            "visible": True,
            })
        return Button(button)

    def wait_until_closed(self):
        self._dialog.wait_until_closed()


_logger = logging.getLogger(__name__)


class _ActiveComboBox:

    def __init__(self, hid: HID, widget: Widget):
        self._widget = widget
        self._hid = hid

    def _open(self):
        self._hid.mouse_left_click_on_object(self._widget)

    def select(self, item_text: str):
        if item_text == str(self._widget.wait_property('currentText')):
            return
        self._open()
        item = self._widget.find_child({'text': item_text})
        self._hid.mouse_left_click(item.center())
