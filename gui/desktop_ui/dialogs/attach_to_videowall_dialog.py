# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.wrappers import BaseWindow
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class AttachToVideoWallDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "QnAttachToVideowallDialog",
            "type": "QnAttachToVideowallDialog",
            "visible": 1,
            "occurrence": 1,
            })
        self._api = api
        self._hid = hid

    def attach_single_screen(self):
        _logger.info('%r: Attach single screen to Video Wall', self)
        area = self._dialog.find_child({'type': 'QnVideowallManageWidget'})
        self._hid.mouse_left_click(area.center().left(60))

    def save_and_close(self):
        _logger.info('%r: Save and close', self)
        ok_button = self._dialog.find_child({
            "text": "OK",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)
        self._dialog.wait_until_closed()

    def wait_until_appears(self) -> 'AttachToVideoWallDialog':
        self._dialog.wait_until_appears()
        return self
