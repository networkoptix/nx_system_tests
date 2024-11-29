# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.testkit import TestKit
from gui.testkit.hid import HID


class WelcomeScreen:

    def __init__(self, api: TestKit, hid: HID):
        self._widget = Widget(api, {'visible': True, 'enabled': True, 'name': 'sessionsScreen'})
        self._hid = hid

    def click_connect_button(self):
        _logger.info('%r: Click connect to server button', self)
        button = self._get_connect_to_server_button()
        self._hid.mouse_left_click(button.bounds().center())

    def _get_connect_to_server_button(self) -> Button:
        button_widget = self._widget.find_child({
            'id': 'customConnectionButton',
            'type': 'Button',
            'visible': True,
            'enabled': True,
            })
        return Button(button_widget)

    def get_server_tile(self, server_name: str) -> '_ServerTile':
        _logger.info('%r: Looking for server tile with name "%s"', self, server_name)
        locator = {'type': 'SessionItem', 'visible': True, 'enabled': True}
        tiles = [_ServerTile(widget, self._hid) for widget in self._widget.find_children(locator)]
        for tile in tiles:
            if tile.get_name() == server_name:
                return tile
        raise RuntimeError(f'Server tile {server_name!r} not found')


class _ServerTile:

    def __init__(self, widget: Widget, hid: HID):
        self._widget = widget
        self._hid = hid

    def activate(self):
        _logger.info('%r: Open server tile', self)
        self._hid.mouse_left_click(self._widget.center())

    def get_name(self) -> str:
        name_label = self._widget.find_child({'id': 'captionText'})
        return name_label.get_text()

    def activate_edit_dialog(self):
        _logger.info('%r: Open edit dialog', self)
        button = self.get_edit_button()
        self._hid.mouse_left_click(button.center())

    def get_edit_button(self) -> Button:
        button = Button(self._widget.find_child({
            'visible': True,
            'type': 'QQuickIconImage',
            'source': 'qrc:////images/edit.png',
            }))
        return button


_logger = logging.getLogger(__name__)
