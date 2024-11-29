# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.testkit import TestKit
from gui.testkit.hid import HID


class WarningDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._hid = hid
        self._widget = Widget(api, {'id': 'content', 'type': 'QQuickRectangle', 'visible': True})

    def _get_button_by_name(self, button_name: str) -> Button:
        button_object = self._widget.find_child({
            'text': button_name,
            'type': 'DialogButton',
            'visible': True,
            })
        return Button(button_object)

    def click_button(self, button_name: str):
        _logger.info('%r: Click button "%s"', self, button_name)
        button = self._get_button_by_name(button_name)
        self._hid.mouse_left_click(button.bounds().center())


_logger = logging.getLogger(__name__)
