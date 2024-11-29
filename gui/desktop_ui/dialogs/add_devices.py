# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QTable
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class AddDevicesDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "DeviceAdditionDialog",
            "type": "nx::vms::client::desktop::DeviceAdditionDialog",
            "visible": 1,
            })
        self._hid = hid

    def _get_address_qline(self):
        stacked_widget = self._dialog.find_child({
            "name": "stackedWidget",
            "type": "QStackedWidget",
            "visible": 1,
            })
        address_qline = stacked_widget.find_child({
            "type": "QLineEdit",
            "unnamed": 1,
            "visible": 1,
            })
        return QLineEdit(self._hid, address_qline)

    def _get_search_button(self):
        button = self._dialog.find_child({
            "name": "searchButton",
            "type": "QPushButton",
            "visible": 1,
            })
        return Button(button)

    def _search_cameras(self, address, user=None, password=None):
        self._get_address_qline().type_text(address)
        if user is not None:
            login_qline = self._dialog.find_child({
                "occurrence": 2,
                "type": "QLineEdit",
                "unnamed": 1,
                "visible": 1,
                })
            QLineEdit(self._hid, login_qline).type_text(user)
        if password is not None:
            password_qline = self._dialog.find_child({
                "name": "passwordEdit_passwordLineEdit",
                "type": "QLineEdit",
                "visible": 1,
                })
            QLineEdit(self._hid, password_qline).type_text(password)
        search_button = self._get_search_button()
        self._hid.mouse_left_click_on_object(search_button)
        search_button.wait_for_accessible(60)

    def _get_search_result_object(self):
        return self._dialog.find_child({
            "name": "searchResultsStackedWidget",
            "type": "QStackedWidget",
            "visible": 1,
            })

    def _add_cameras(self, address, camera_names, user=None, password=None):
        # Cameras added in one batch should have same credentials.
        self._search_cameras(address, user, password)
        table_object = self._get_search_result_object().find_child({
            "name": "foundDevicesTable",
            "type": "nx::vms::client::desktop::SimpleSelectionTableView",
            "visible": 1,
            })
        table = QTable(self._hid, table_object, ['brand', 'model', 'address', 'selection_box'])
        for name in camera_names:
            row = table.find_row(model=name)
            if not row.cell('selection_box').is_checked():
                row.leftmost_cell().click()
        add_devices_button = self._get_search_result_object().find_child({
            "name": "addDevicesButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(add_devices_button)
        self._dialog.close()

    def add_test_cameras(self, address, camera_names):
        # Inside method to start test cameras there is a hardcoded port for discovery. Use it here.
        _logger.info('%r: Add cameras %s with address %s', self, camera_names, address)
        self._add_cameras(f"{address}:4983", camera_names)
