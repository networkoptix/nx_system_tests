# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.dialogs.camera_settings import CameraSettingsDialog
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QMenu
from gui.desktop_ui.wrappers import QTable
from gui.desktop_ui.wrappers import TabWidget
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class ServerSettingsDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "ServerSettingsDialog",
            "type": "QnServerSettingsDialog",
            "visible": 1,
            })
        self._hid = hid
        self.general_tab = _GeneralSettingsTab(self._dialog, hid)
        self.storage_management_tab = _StorageManagementTab(self._dialog, api, hid)
        self.analytics_tab = _AnalyticsTab(self._dialog, api, hid)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.save()

    def activate_tab(self, tab_name):
        _logger.info('%r: Activate tab %s', self, tab_name)
        tab_bar = self._dialog.find_child({
            "name": "tabWidget",
            "type": "QTabWidget",
            "visible": 1,
            "occurrence": 1,
            })
        tab = TabWidget(tab_bar).find_tab(tab_name)
        self._hid.mouse_left_click_on_object(tab)

    def open_storage_management_tab(self):
        self.activate_tab('Storage Management')

    def open_general_tab(self):
        self.activate_tab('General')

    def open_analytics_tab(self):
        self.activate_tab('Storage Analytics')

    def save(self):
        _logger.info('%r: Save and close', self)
        ok_button = self._dialog.find_child({
            "text": "OK",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)
        self._dialog.wait_until_closed()

    def rename(self, name):
        _logger.info('%r: Rename server to %s', self, name)
        self.general_tab.set_server_name(name)
        return self

    def wait_until_appears(self) -> 'ServerSettingsDialog':
        self._dialog.wait_until_appears()
        return self

    def close(self):
        self._dialog.close()

    def is_open(self):
        return self._dialog.is_open()


class _GeneralSettingsTab:

    def __init__(self, dialog: BaseWindow, hid: HID):
        self._dialog = dialog
        self._hid = hid

    def set_server_name(self, name: str):
        tab = self._dialog.find_child({
            "name": "ServerSettingsWidget",
            "type": "QnServerSettingsWidget",
            "visible": 1,
            })
        server_name_field = tab.find_child({
            "name": "nameLineEdit",
            "type": "QLineEdit",
            "visible": 1,
            })
        QLineEdit(self._hid, server_name_field).type_text(name)


class _StorageManagementTab:

    def __init__(self, dialog: BaseWindow, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._dialog = dialog

    def _get_storage_box(self):
        return self._dialog.find_child({
            "name": "storagesGroupBox",
            "type": "QGroupBox",
            "visible": 1,
            })

    def backup(self):
        # TODO There is no such button anymore. Resolve when DESIGN-820 finished.
        _logger.info('%r: Start archive backup', self)
        start_backup_button = self._dialog.find_child({
            "name": "backupStartButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(start_backup_button)
        MessageBox(self._api, self._hid).wait_until_has_label('Archive backup completed').close()

    def initiate_archives_rebuilding(self):
        _logger.info('%r: Start archives rebuilding', self)
        reindex_archive_button = self._get_storage_box().find_child({
            "name": "rebuildMainButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(reindex_archive_button)
        MessageBox(self._api, self._hid).wait_until_has_label('Hard disk load will increase significantly')

    def is_rebuilding_started(self):
        stop_rebuilding_archive = self._get_storage_box().find_child({
            "name": "stopButton",
            "type": "QPushButton",
            "visible": 1,
            })
        return Button(stop_rebuilding_archive).is_accessible()

    def _get_table(self):
        table_object = self._dialog.find_child({
            "name": "storageView",
            "type": "nx::vms::client::desktop::TreeView",
            "visible": 1,
            })
        return QTable(self._hid, table_object, ['path', 'location', 'purpose', 'size', 'analytics', '???', 'enabled'])

    def list_storages(self):
        return [_StorageRow(row) for row in self._get_table().all_rows()]

    def get_storage(self, path):
        _logger.info('%r: Get storage %s', self, path)
        row = self._get_table().find_row(path=path)
        return _StorageRow(row)


class _StorageRow:

    def __init__(self, row):
        self._row = row

    def _is_enabled(self):
        enabled_cell = self._row.cell('enabled')
        return enabled_cell.is_checked()

    def disable(self):
        _logger.info('%r:-%s: Disable row', self, self._row)
        if self._is_enabled():
            self._row.cell('enabled').click()

    def enable(self):
        _logger.info('%r:-%s: Enable row', self, self._row)
        if not self._is_enabled():
            self._row.cell('enabled').click()


class _AnalyticsTab:

    def __init__(self, dialog: BaseWindow, api: TestKit, hid: HID):
        self._dialog = dialog
        self._hid = hid
        self._api = api

    def open_camera_settings(self, index) -> CameraSettingsDialog:
        _logger.info('%r: Open Camera Settings Dialog', self)
        cameras_table_object = self._dialog.find_child({
            "name": "statsTable",
            "type": "nx::vms::client::desktop::TableView",
            "visible": 1,
            })
        cameras_table = QTable(self._hid, cameras_table_object, ['camera', 'space', 'time', 'bitrate'])
        cell = cameras_table.row(index).leftmost_cell()
        # Activate context menu
        cell.right_click()
        # Open Camera Settings...
        QMenu(self._api, self._hid).activate_items("Camera Settings...", timeout=5)
        return CameraSettingsDialog(self._api, self._hid).wait_until_appears()
