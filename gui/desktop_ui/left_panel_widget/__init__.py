# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui.desktop_ui.main_window import get_control_layer
from gui.desktop_ui.main_window import get_main_window_widget
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class LeftPanelWidget:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._obj = Widget(api, {
            "type": "nx::vms::client::desktop::QmlResourceBrowserWidget",
            "unnamed": 1,
            "visible": 1,
            "window": {
                "type": "nx::vms::client::desktop::MainWindow",
                "unnamed": 1,
                "visible": 1,
                },
            })
        # Maximum and minimum width do not depend on screen resolution.
        self.resource_browser_max_width = 480
        self.resource_browser_min_width = 200
        # Visible part of the resize widget.
        self.resize_widget_width = 1

    def _get_resize_widget(self):
        # TODO: Now find_child falls down as there are 5 objects found by this locator.
        #  Have to investigate why filtering by height, width, y and z parameters do not work
        window_height = get_main_window_widget(self._api).bounds().height
        widget = get_control_layer(self._api).find_child({
            "acceptDrops": "no",
            "enabled": "yes",
            "focusable": "no",
            "height": window_height,
            "movable": "yes",
            "selectable": "no",
            "type": "GraphicsWidget",
            "visible": "yes",
            "width": 8,
            "y": 0,
            "z": 2,
            })
        return widget

    def _get_button(self, name: str):
        button = get_control_layer(self._api).find_child({
            "acceptDrops": "no",
            "enabled": "yes",
            "focusable": "yes",
            "movable": "no",
            "selectable": "no",
            "toolTip": f"{name.capitalize()} Tree<b></b>",
            "type": "QnImageButtonWidget",
            "visible": "yes",
            })
        return Button(button)

    def show(self):
        _logger.info('%r: Show', self)
        if not self.is_shown():
            self._hid.mouse_left_click_on_object(self._get_button('Show'))
            time.sleep(1)
            if not self.is_shown():
                raise RuntimeError('Left panel still hidden')

    def hide(self):
        _logger.info('%r: Hide', self)
        if self.is_shown():
            self._hid.mouse_left_click_on_object(self._get_button('Hide'))
            time.sleep(1)
            if self.is_shown():
                raise RuntimeError('Left panel still shown')

    def is_shown(self):
        """Return if left panel is visible or not.

        Visibility check via 'visible' property does not work for left panel.
        However, when desktop client is in window mode when left panel is shown
        its x coordinate is equal to 0, and when it is in full screen mode
        x coordinate value is more than 0.
        """
        return self._obj.bounds().x >= 0

    def resize_to_max(self):
        _logger.info('%r: Resize to maximum', self)
        resize_widget_coords = self._get_resize_widget().center()
        self._hid.mouse_drag_and_drop(
            resize_widget_coords,
            resize_widget_coords.right(self.resource_browser_max_width),
            )

    def resize_to_min(self):
        _logger.info('%r: Resize to minimum', self)
        resize_widget_coords = self._get_resize_widget().center()
        self._hid.mouse_drag_and_drop(
            resize_widget_coords,
            resize_widget_coords.right(self.resource_browser_max_width),
            )
