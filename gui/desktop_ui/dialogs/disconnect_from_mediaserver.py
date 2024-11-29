# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.messages import MessageBox
from gui.testkit import TestKit
from gui.testkit.hid import HID


class DisconnectFromMediaserverDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._confirmation = MessageBox(api, hid)

    def is_shown(self) -> bool:
        if not self._confirmation.is_accessible():
            _logger.error('Message box was not found')
            return False
        window_title = self._confirmation.get_window_title()
        if window_title != 'Disconnect':
            raise RuntimeError(
                f'Unexpected Message Box title. Current: {window_title!r}. Expected: "Disconnect"',
                )
        return True

    def click_disconnect(self):
        self._confirmation.click_button_with_text('Disconnect')


_logger = logging.getLogger(__name__)
