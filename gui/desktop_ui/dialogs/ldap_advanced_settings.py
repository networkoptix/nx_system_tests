# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
from enum import Enum

from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.testkit import TestKit
from gui.testkit.hid import HID


class SynchronizeUsersState(Enum):
    ALWAYS = 'Always'
    ON_LOG_IN = 'On Log In'


class LDAPAdvancedSettingsDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._widget = Widget(
            api, {'type': 'AdvancedSettingsDialog', 'enabled': True, 'visible': True})
        self._hid = hid

    def get_synchronize_users_state(self) -> SynchronizeUsersState:
        locator = {
            'id': 'contentItem',
            'text': re.compile('Always|On Log In'),
            'visible': True,
            }
        combo_box = self._widget.find_child(locator)
        state_text = combo_box.get_text()
        return SynchronizeUsersState(state_text)

    def click_ok(self):
        _logger.info('%r: Click OK button', self)
        button = Button(self._widget.find_child({
            'text': 'OK',
            'type': 'Button',
            'visible': True,
            'enabled': True,
            }))
        self._hid.mouse_left_click(button.center())


_logger = logging.getLogger(__name__)
