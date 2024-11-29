# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import ComboBox
from gui.desktop_ui.wrappers import QLineEdit
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class NewVirtualCameraDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "NewVirtualCameraDialog",
            "type": "QnNewVirtualCameraDialog",
            "visible": 1,
            })
        self._hid = hid

    def get_available_servers(self) -> list:
        return self._server_combo_box().get_list()

    def add_virtual_camera(self, camera_name=None, server_name=None):
        _logger.info(
            '%r: Add new virtual camera with name %s',
            self, camera_name)
        self._dialog.wait_for_accessible()
        if camera_name is not None:
            self._camera_name_box().type_text(camera_name)
        if server_name is not None:
            self._server_combo_box().select(server_name)
        ok_button = self._dialog.find_child({
            "text": "OK",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)
        self._dialog.wait_until_closed()

    def get_current_camera_name(self) -> str:
        self._dialog.wait_for_accessible()
        return self._camera_name_box().get_text()

    def get_current_server_name(self) -> str:
        self._dialog.wait_for_accessible()
        return self._server_combo_box().current_item()

    def _camera_name_box(self):
        return QLineEdit(self._hid, self._dialog.find_child({
            "type": "QLineEdit",
            "unnamed": 1,
            "visible": 1,
            }))

    def _server_combo_box(self):
        return ComboBox(self._hid, self._dialog.find_child({
            "name": "serverComboBox",
            "type": "QComboBox",
            "visible": 1,
            }))

    def wait_until_appears(self) -> 'NewVirtualCameraDialog':
        self._dialog.wait_until_appears()
        return self
