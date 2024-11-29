# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from datetime import datetime
from typing import NamedTuple
from typing import Union

from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QTable
from gui.desktop_ui.wrappers import TabWidget
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class AuditTrail(BaseWindow):

    def __init__(self, api: TestKit, hid: HID):
        super().__init__(api=api, locator_or_obj={
            "name": "AuditLogDialog",
            "type": "QnAuditLogDialog",
            "visible": 1,
            "occurrence": 1,
            })
        self._hid = hid

    def _get_tab_widget(self):
        tab_widget = self.find_child({
            "name": "mainTabWidget",
            "type": "QTabWidget",
            "visible": 1,
            })
        return TabWidget(tab_widget)

    @classmethod
    def open(cls, api: TestKit, hid: HID) -> 'AuditTrail':
        MainMenu(api, hid).activate_audit_trail()
        return AuditTrail(api, hid).wait_until_appears()

    def set_tab(self, tab_name):
        _logger.info('%r: Set tab %s', self, tab_name)
        tab = self._get_tab_widget().find_tab(tab_name)
        self._hid.mouse_left_click_on_object(tab)

    def get_current_tab(self):
        index = self._get_tab_widget().get_current_index()
        if index == 0:
            return 'Sessions'
        elif index == 1:
            return 'Cameras'
        else:
            raise RuntimeError(f"Unknown tab with index {index}")

    def search(self, text):
        _logger.info('%r: Set search text: %s', self, text)
        search_panel = self.find_child({
            "type": "QLineEdit",
            "unnamed": 1,
            "visible": 1,
            })
        QLineEdit(self._hid, search_panel).type_text(text)


class AuditTrailSessionsTable:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        audit_trail = AuditTrail(api, hid)
        if not audit_trail.get_current_tab() == 'Sessions':
            audit_trail.set_tab('Sessions')

    _datetime_format = '%m/%d/%Y' + ' ' + '%I:%M:%S %p'

    def _get_table(self):
        table_object = AuditTrail(self._api, self._hid).find_child({
            "name": "gridMaster",
            "type": "nx::vms::client::desktop::CheckableTableView",
            "visible": 1,
            })
        return QTable(self._hid, table_object, [None, 'session_begins', 'session_ends', 'duration', 'user', 'ip', 'activity'])

    def session_begins(self, row_i) -> Union[datetime, str]:
        cell_text = self._get_table().row(row_i).cell('session_begins').get_display_text()
        return datetime.strptime(cell_text, self._datetime_format) if cell_text else ''

    def session_ends(self, row_i) -> str:
        return self._get_table().row(row_i).cell('session_ends').get_display_text()

    def duration(self, row_i) -> str:
        return self._get_table().row(row_i).cell('duration').get_display_text()

    def user(self, row_i) -> str:
        return self._get_table().row(row_i).cell('user').get_display_text()

    def ip(self, row_i) -> str:
        return self._get_table().row(row_i).cell('ip').get_display_text()

    def activity(self, row_i) -> str:
        cell = self._get_table().row(row_i).cell('activity')
        return cell.get_display_text()


class _CameraInAuditTrail(NamedTuple):
    ip: str
    activity: str


class AuditTrailCamerasTable:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        audit_trail = AuditTrail(api, hid)
        if not audit_trail.get_current_tab() == 'Cameras':
            audit_trail.set_tab('Cameras')

    def _get_table(self):
        table_object = AuditTrail(self._api, self._hid).find_child({
            "name": "gridCameras",
            "type": "nx::vms::client::desktop::CheckableTableView",
            "visible": 1,
            })
        return QTable(self._hid, table_object, [None, 'camera_name', 'ip', 'activity'])

    def count_rows(self):
        return len(self._get_table().all_rows())

    def is_empty(self) -> bool:
        return not self._get_table().is_accessible_timeout(0.5)

    def has_camera(self, camera_name):
        _logger.info('%r: Looking for camera with name %s', self, camera_name)
        row_i = self._get_table().get_row_index_by_values(camera_name=camera_name)
        return row_i is not None

    def get_camera(self, camera_name):
        _logger.info('%r: Looking for camera with name %s', self, camera_name)
        row_i = self._get_table().get_row_index_by_values(camera_name=camera_name)
        if row_i is None:
            raise ValueError("Camera %s not found in AuditTrailCamerasTable")
        return _CameraInAuditTrail(
            self._get_table().row(row_i).cell('ip').get_display_text(),
            self._get_table().row(row_i).cell('activity').get_display_text(),
            )


class AuditTrailDetailsTable:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid

    def _get_table(self):
        table_object = AuditTrail(self._api, self._hid).find_child({
            "name": "gridDetails",
            "type": "nx::vms::client::desktop::TableView",
            "visible": 1,
            })
        return QTable(self._hid, table_object, ['date', 'time', 'user', 'ip', 'activity', 'description'])

    def is_empty(self) -> bool:
        return not self._get_table().is_accessible_timeout(0.5)
