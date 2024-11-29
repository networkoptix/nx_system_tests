# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
from typing import Sequence

from gui.desktop_ui.screen import ScreenRectangle
from gui.desktop_ui.widget import Widget
from gui.mobile_ui.video_screen import VideoScreen
from gui.testkit import TestKit
from gui.testkit.hid import ClickableObject
from gui.testkit.hid import HID


class Scene:

    def __init__(self, api: TestKit, hid: HID):
        locator = {'type': 'ResourcesScreen', 'visible': True, 'enabled': True}
        self._widget = Widget(api, locator)
        self._hid = hid
        self._api = api

    def wait_for_accessible(self):
        self._widget.wait_for_accessible(5)
        self._get_title_widget().wait_for_accessible()

    def get_camera_items(self) -> Sequence['_CameraSceneItem']:
        _logger.info('%r: Looking for camera scene items', self)
        widgets = self._widget.find_children({'type': 'CameraItem', 'visible': True})
        return [_CameraSceneItem(widget, self._hid) for widget in widgets]

    def get_title_text(self) -> str:
        title_label = self._get_title_widget()
        return title_label.get_text()

    def open_camera_item(self, name: str) -> VideoScreen:
        _logger.info('%r: Open Camera Scene Item "%s"', self, name)
        item = self._get_camera_item(name)
        self._hid.mouse_left_click_on_object(item)
        video_screen = VideoScreen(self._api, self._hid)
        video_screen.wait_for_accessible()
        return video_screen

    def _get_camera_item(self, name: str) -> '_CameraSceneItem':
        for item in self.get_camera_items():
            if item.name() == name:
                return item
        raise RuntimeError(f'Camera scene item with name {name!r} not found')

    def _get_title_widget(self) -> Widget:
        # Title label can exist but be empty or contain the "." symbol. Ignore it in such cases.
        title_label = self._widget.find_child({
            'type': 'PageTitleLabel',
            'visible': True,
            'text': re.compile(r'[A-Za-z0-9]+'),
            })
        return title_label

    def get_placeholder_text(self) -> str:
        text_widget = self._widget.find_child({
            'visible': True,
            'id': 'title',
            'type': 'QQuickText',
            })
        return text_widget.get_text()

    def activate_show_all_cameras_button(self):
        _logger.info('%r: Activate "Show all cameras" button', self)
        button_widget = self._widget.find_child({
            'visible': True,
            'enabled': True,
            'id': 'button',
            'text': 'Show all cameras',
            })
        self._hid.mouse_left_click(button_widget.center())


class _CameraSceneItem(ClickableObject):

    def __init__(self, widget: Widget, hid: HID):
        self._widget = widget
        self._hid = hid

    def name(self) -> str:
        return self._widget.get_text()

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()


_logger = logging.getLogger(__name__)
