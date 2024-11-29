# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from typing import Collection

from gui.desktop_ui.main_window import get_graphics_view_object
from gui.desktop_ui.media_capturing import ImageCapture
from gui.desktop_ui.screen import ScreenPoint
from gui.desktop_ui.screen import ScreenRectangle
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QLabel
from gui.desktop_ui.wrappers import QSpinBox
from gui.testkit import TestKit
from gui.testkit.hid import ClickableObject
from gui.testkit.hid import ControlModifier
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class Showreel:
    """Showreel container is just piled in QnGraphicsView, not any special.

    The class is meant to provide object-style access to such objects.
    """

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid

    def has_item(self, name):
        _logger.info('%r: Looking for item: %s', self, name)
        try:
            self.get_item(name)
            return True
        except RuntimeError as e:
            if f"Cannot find showreel with name {name}" in str(e):
                return False

    def get_item(self, name):
        _logger.info('%r: Looking for item: %s', self, name)
        for item in self._get_items_unordered():
            if name in item.get_label_texts():
                return item
        raise RuntimeError(f"Cannot find showreel with name {name}")

    def _get_placeholders_unordered(self):
        return get_graphics_view_object(self._api).find_children({
            'type': 'nx::vms::client::desktop::ShowreelDropPlaceholder',
            })

    def get_items(self):
        items = self._get_items_unordered()
        return self._sort_items(items)

    def count_items(self):
        """Count but don't sort items."""
        return len(self._get_items_unordered())

    def _get_items_unordered(self):
        objects = get_graphics_view_object(self._api).find_children({
            'type': 'nx::vms::client::desktop::ShowreelItemWidget',
            })
        return [_ShowreelItem(obj, self._hid, self._api) for obj in objects]

    def _get_name_label(self):
        label = Widget(self._api, {
            'visible': True,
            'name': 'captionLabel',
            'type': 'QLabel',
            })
        return QLabel(label)

    def get_showreel_name(self):
        return self._get_name_label().get_text()

    def get_first_placeholder_coords(self) -> ScreenPoint:
        items = self._get_placeholders_unordered()
        ordered = self._sort_items(items)  # TODO: Is ordering necessary?
        return ordered[0].bounds().center()

    def get_first_item_coords(self) -> ScreenPoint:
        item = self.get_items()[0]
        return item.bounds().center()

    def get_title_coords(self) -> ScreenRectangle:
        return self._get_name_label().bounds()

    def get_empty_place_coords(self) -> ScreenPoint:
        empty = self._get_placeholders_unordered()
        non_empty = self._get_items_unordered()
        items = self._sort_items([*empty, *non_empty])
        return items[-1].bounds().bottom_left().down(30)

    @staticmethod
    def _sort_items(items):
        ordering = []
        for [index, item] in enumerate(items):
            # Call .bounds() once per item. Avoid repeated external calls.
            bounds = item.bounds()
            # Add index. If coordinates are equal, Python produces an error
            # when comparing objects, which don't implement comparison.
            ordering.append((bounds.y, bounds.x, index, item))
        ordering.sort()
        return [item for [_, _, _, item] in ordering]

    def get_item_names(self):
        time.sleep(0.5)
        items = self.get_items()
        return [item.get_title() for item in items]

    def start(self):
        _logger.info('%r: Start', self)
        start_button = Button(Widget(self._api, {
            "text": "Start Showreel",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            }))
        self._hid.mouse_left_click_on_object(start_button)

    def click_empty_space(self):
        _logger.info('%r: Click empty place', self)
        self._hid.mouse_left_click_on_object(self._get_name_label())


class _ShowreelItem(ClickableObject):
    # nx::vms::client::desktop::ui::workbench::LayoutTourItemWidget

    def __init__(self, obj: Widget, hid: HID, api: TestKit):
        self._obj = obj
        self._hid = hid
        self._api = api

    def get_title(self) -> str:
        # Used more name keys to speed up method.
        return self.get_label_texts()[0]

    def _get_display_time_spinbox(self) -> QSpinBox:
        """Find display time spinbox by its position.

        It is impossible to find spinbox as a child of the showreel widget.
        Search for it from the root widget and choose
        the correct one by its position.
        TODO: Update this method after fix: https://networkoptix.atlassian.net/browse/VMS-47747
        """
        spin_boxes_objs = self._api.find_objects({
            'type': 'QSpinBox',
            'visible': True,
            })
        bounds = self.bounds()
        for spin_box_obj in spin_boxes_objs:
            spin_box = QSpinBox(self._hid, Widget(self._api, spin_box_obj))
            if bounds.contains_rectangle(spin_box.bounds()):
                return spin_box
        raise RuntimeError("Display time spinbox not found")

    def get_label_texts(self) -> Collection[str]:
        label_objects = self._obj.find_children({'type': 'GraphicsLabel', 'visible': 'yes'})
        return [obj.get_text() for obj in label_objects]

    def is_selected(self) -> bool:
        return bool(self._obj.wait_property('selected'))

    def get_display_time(self) -> int:
        text = self._get_display_time_spinbox().get_text()
        if not text.endswith(' s'):
            raise RuntimeError("Unexpected display time text value")
        return int(text[:-2])

    def set_display_time(self, value: int):
        _logger.info('%r: Set display time: %s seconds', self, value)
        # The spinbox displaying time has a specific format: "{value} s".
        # Using QSpinBox().type_text() is not viable due to internal result checking.
        spin_box = self._get_display_time_spinbox()
        spin_box.clear_field()
        self._hid.write_text(str(value))

    def image_capture(self) -> ImageCapture:
        # It seems impossible to get only the camera, server in the tile. So this is a whole tile.
        return self._obj.image_capture()

    def click(self):
        _logger.info('%r: Click', self)
        self._hid.mouse_left_click_on_object(self)

    def right_click(self):
        _logger.info('%r: Right click', self)
        self._hid.mouse_right_click_on_object(self)

    def ctrl_click(self):
        _logger.info('%r: Ctrl click', self)
        self._hid.mouse_left_click_on_object(self, modifier=ControlModifier)

    def bounds(self) -> ScreenRectangle:
        return self._obj.bounds()
