# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import QTable
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class CameraListDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "CameraListDialog",
            "type": "QnCameraListDialog",
            "visible": 1,
            })
        self._hid = hid

    def _get_table(self):
        table = self._dialog.find_child({
            "name": "camerasView",
            "type": "nx::vms::client::desktop::TableView",
            "visible": 1,
            })
        return QTable(self._hid, table, [
            'Recording',
            'Name',
            'Vendor',
            'Model',
            'Firmware',
            'IP/Name',
            'MAC address',
            'ID',
            'Server',
            ])

    def close(self):
        _logger.info('%r: Close Camera List Dialog', self)
        self._dialog.close()

    def wait_until_appears(self, timeout: float = 10):
        _logger.info(
            '%r: Wait for Camera List Dialog appears. Timeout %s second(s)',
            self, timeout)
        self._dialog.wait_until_appears(timeout)

    def get_id_for_camera(self, camera_name):
        _logger.info('%r: Getting ID for camera %s', self, camera_name)
        table = self._get_table()
        row = table.find_row(Name=camera_name)
        cell = row.cell('ID').get_text()
        return int(cell)
