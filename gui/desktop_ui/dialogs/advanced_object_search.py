# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from enum import Enum
from typing import Mapping
from typing import Sequence

from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import NumberInput
from gui.desktop_ui.wrappers import QLineEdit
from gui.testkit.hid import HID
from gui.testkit.testkit import TestKit

_logger = logging.getLogger(__name__)


class AnalyticObjectTypesNames(Enum):
    animal = "Animal"
    person = "Person"
    base1 = "Stub: Base Object Type 1"
    base2 = "Stub: Base Object Type 2"
    live_only = "Stub: Live-only Object Type"
    non_indexable = "Stub: Non-indexable Object Type"
    from_engine_manifest = "Stub: Object Type from Engine Manifest"
    custom_with_base_color_type = "Stub: Custom Type using Base Type Library Color Type"
    custom_with_base_enum_type = "Stub: Custom Type using Base Type Library Enum Type"
    custom_with_base_object_type = "Stub: Custom Type using Base Type Library Object Type"
    with_attribute_list = "Stub: Object Type with Attribute List"
    with_boolean_attributes = "Stub: Object Type with Boolean attributes"
    with_icon = "Stub: Object Type with icon"
    with_numeric_attributes = "Stub: Object Type with Number attributes"


class AdvancedObjectSearchDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            'visible': True,
            'type': 'AnalyticsSearchDialog',
            'title': 'Advanced Object Search',
            'occurrence': 1,
            'text': '',
            })
        self._api = api
        self._hid = hid

    def wait_until_appears(self) -> 'AdvancedObjectSearchDialog':
        self._dialog.wait_until_appears()
        return self

    def _get_camera_filter_button_by_text(self, text) -> Widget:
        return self._dialog.find_child({
            'visible': True,
            'type': 'QQuickText',
            'occurrence': 1,
            'text': text,
            })

    def set_filter_any_camera(self):
        _logger.info('%r: Set camera filter to "Any camera', self)
        menu_locator_6_0 = {
            "type": 'MenuItem',
            "unnamed": 1,
            "visible": 1,
            "text": "Any camera",
            }
        menu_locator_6_1 = {
            "type": 'CompactMenuItem',
            "visible": 1,
            "text": "Any camera",
            }
        any_camera_filter = Widget(self._api, menu_locator_6_0)
        if not any_camera_filter.is_accessible():
            any_camera_filter = Widget(self._api, menu_locator_6_1)
        self._hid.mouse_left_click_on_object(any_camera_filter)

    def click_filter_with_text(self, text):
        button = self._get_camera_filter_button_by_text(text)
        self._hid.mouse_left_click_on_object(button)

    def get_tiles_with_text(self, text) -> Sequence[Widget]:
        return self._dialog.find_children({
            'visible': True,
            'type': 'QQuickText',
            'id': 'caption',
            'text': text,
            })

    def wait_for_no_tiles_with_title(self, title: str):
        start_time = time.monotonic()
        while True:
            if not self.get_tiles_with_text(title):
                return
            elif time.monotonic() - start_time > 10:
                raise RuntimeError(
                    f"Tiles with title {title} are seen in Advanced Object Search")
            time.sleep(.1)

    def wait_for_tiles_with_title(self, title: str):
        start_time = time.monotonic()
        while True:
            if self.get_tiles_with_text(title):
                return
            elif time.monotonic() - start_time > 15:
                raise RuntimeError(
                    f"No tiles with title {title} "
                    f"are seen in Advanced Object Search")
            time.sleep(.1)

    def get_show_on_layout_button(self):
        button = self._dialog.find_child({
            'text': 'Show on Layout',
            'type': 'Button',
            })
        return Button(button)

    def get_object_type_button_object(self, name: str):
        return self._dialog.find_child({
            "text": name,
            "type": "OptionButton",
            "visible": True,
            })

    def click_object_type_button(self, name: str):
        button = self.get_object_type_button_object(name)
        self._hid.mouse_left_click_on_object(button)

    def get_object_type_icon(self, name: str):
        return self.get_object_type_button_object(name).find_child({
            'id': 'iconImage',
            })

    def get_all_filter_blocks(self, collapsible: bool = False):
        modules = {}
        module_objects = self._dialog.find_children({"type": "CollapsiblePanel"})
        for module in module_objects:
            if collapsible:
                buttons = module.find_children({"type": "TextButton", 'id': 'nameButton'})
                for button in buttons:
                    title = button.get_text()
                    modules[title] = _FilterBlock(module, title, self._hid)
            else:
                module.wait_for_object()
                title = module.find_child({"type": "TextButton", 'id': 'nameButton'}).get_text()
                modules[title] = _FilterBlock(module, title, self._hid)
        return modules

    def close(self):
        self._dialog.close()


class _FilterBlock:

    def __init__(self, module: Widget, name: str, hid: HID):
        self._name = name
        self._module = module
        self._hid = hid

    def click_header(self):
        header = self._module.find_child({
            'text': self._name,
            'visible': True,
            'type': 'TextButton',
            })
        self._hid.mouse_left_click_on_object(header)
        # Here we need to await animation to expand/collapse a header
        time.sleep(.3)

    def get_string_attribute_field(self) -> QLineEdit:
        field = self._module.find_child({"type": "StringEditor"})
        return QLineEdit(self._hid, field)

    def get_number_attribute_fields(self) -> [NumberInput, NumberInput]:
        start_field, end_field = self._module.find_children({"type": "NumberInput"})
        return [NumberInput(start_field, self._hid), NumberInput(end_field, self._hid)]

    def get_radiobuttons_with_names(self) -> Mapping[str, Button]:
        buttons = {}
        buttons_objects = self._module.find_children({
            "type": "RadioButton",
            "visible": True,
            })
        for button in buttons_objects:
            buttons[button.get_text()] = Button(button)
        return buttons
