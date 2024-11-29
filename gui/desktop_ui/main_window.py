# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui.desktop_ui.wrappers import BaseWindow
from gui.testkit import ObjectNotFound
from gui.testkit import TestKit
from gui.testkit import TestKitConnectionError
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class MainWindow:

    def __init__(self, api: TestKit, hid: HID):
        self._base_window = get_main_window_widget(api)
        self._api = api
        self._hid = hid

    def activate(self):
        start = time.monotonic()
        while True:
            try:
                self._base_window.activate()
                # TODO: Try move client to the foreground from C++ code.
                # There are 2 methods in TestKit: activate() and activateWindow(),
                # but they don't work properly.
                self._hid.mouse_left_click(self._base_window.bounds().top_center().down(10))
                return
            except ObjectNotFound:
                _logger.info('Client not ready yet')
                self._api.reset_cache()
            if time.monotonic() - start > 20:
                raise RuntimeError('Client is not ready for testing')
            time.sleep(1)

    def hover_away(self):
        """Move mouse to avoid hovering anything."""
        self._hid.mouse_move(self._base_window.bounds().top_left())

    def image_capture(self):
        return self._base_window.image_capture()

    def is_fullscreen(self):
        return self._base_window.wait_property('fullScreen')

    def put_in_fullscreen_mode(self):
        _logger.info('%r: Put in full-screen mode', self)
        if not self.is_fullscreen():
            button = self.find_child({
                "text": "Go to Fullscreen",
                "type": "nx::vms::client::desktop::ToolButton",
                "unnamed": 1,
                "visible": 1,
                })
            self._hid.mouse_left_click_on_object(button)
            # Wait until main window become available.
            self._wait_for_accessible()

    def wait_for_screen_mode(self, fullscreen=True, timeout: float = 3):
        _logger.info(
            '%r: Wait until screen mode: Full-screen=%s. Timeout: %s second(s)',
            self, fullscreen, timeout)
        start_time = time.monotonic()
        while True:
            if self.is_fullscreen() == fullscreen:
                return
            if time.monotonic() - start_time > timeout:
                if fullscreen:
                    raise RuntimeError("Client is not in fullscreen")
                raise RuntimeError("Client is not in window mode")
            time.sleep(1)

    def put_in_window_mode(self):
        _logger.info('%r: Put in window mode', self)
        if self.is_fullscreen():
            button = self.find_child({
                "text": "Exit Fullscreen",
                "type": "nx::vms::client::desktop::ToolButton",
                "unnamed": 1,
                "visible": 1,
                })
            self._hid.mouse_left_click_on_object(button)
            # Wait until main window become available.
            self._wait_for_accessible()

    def close_client_by_cross(self):
        """Close a client from MainWindow.

        Needed for Session restore feature.
        Creates a general session restore file unlike sq.applicationContextList().detach().
        """
        _logger.info('%r: Close client by cross button', self)
        cross_button = self.find_child({
            "text": "Exit",
            "type": "nx::vms::client::desktop::ToolButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(cross_button)
        try:
            self._base_window.wait_until_closed()
        except TestKitConnectionError:
            _logger.info('%r: Desktop Client is closed', self)

    def resize(self, width: int, height: int):
        _logger.info('%r: Set size: width %s, height %s', self, width, height)
        self._wait_for_object().call_method('resize', width, height)

    def resize_width(self, width: int):
        _logger.info('%r: Set width: %s', self, width)
        bounds = self._base_window.bounds()
        height = bounds.height
        self._wait_for_object().call_method('resize', width, height)

    def bounds(self):
        return self._base_window.bounds()

    def _wait_for_object(self):
        return self._base_window.wait_for_object()

    def _wait_for_accessible(self):
        self._base_window.wait_for_accessible()

    def find_child(self, locator: dict):
        return self._base_window.find_child(locator)


def get_main_window_widget(api: TestKit) -> BaseWindow:
    return BaseWindow(api=api, locator_or_obj={
        "type": "nx::vms::client::desktop::MainWindow",
        "unnamed": 1,
        "visible": 1,
        })


def get_graphics_view_object(api: TestKit):
    return get_main_window_widget(api).find_child({
        "type": "QnGraphicsView",
        "unnamed": 1,
        "visible": 1,
        })


def get_control_layer(api: TestKit):
    return get_graphics_view_object(api).find_child({
        "acceptDrops": "no",
        "enabled": "yes",
        "focusable": "no",
        "movable": "no",
        "objectName": "UIControlsLayer",
        "selectable": "no",
        "type": "QnGuiElementsWidget",
        "visible": "yes",
        })
