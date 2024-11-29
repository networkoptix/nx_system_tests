# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from typing import Literal

from gui.desktop_ui.layouts import LayoutNameDialog
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.wrappers import Button
from gui.testkit import TestKit
from gui.testkit.hid import HID


class VideowallCreationDialog:

    def __init__(self, api: TestKit, hid: HID, close_by: Literal['OK', 'Cancel'] = 'OK'):
        self._api = api
        self._hid = hid
        self._new_videowall_dialog = LayoutNameDialog(api, hid)
        self._closing_button_text = close_by

    def __enter__(self):
        time.sleep(.5)
        MainMenu(self._api, self._hid).activate_new_videowall()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._hid.mouse_left_click_on_object(self._get_button_by_text(self._closing_button_text))
            self._new_videowall_dialog.dialog.wait_until_closed()

    def _get_button_by_text(self, button_text: str):
        # There is a Client bug with duplicate buttons. It occurs rarely, and probably it is a Qt bug.
        # Once it is fixed, it will be necessary to replace find_children() with find_child().
        # See: https://networkoptix.atlassian.net/browse/VMS-47626
        buttons = self._new_videowall_dialog.dialog.find_children({
            "text": button_text,
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        if len(buttons) > 1:
            _logger.warning("Buttons with the text '%s' were found: %i", button_text, len(buttons))
        return Button(buttons[0])

    def insert_name(self, name):
        self._new_videowall_dialog.get_name_field().type_text(name)

    def ok_button_is_active(self) -> bool:
        return self._get_button_by_text('OK').is_accessible()


_logger = logging.getLogger(__name__)
