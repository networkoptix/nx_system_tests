# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re

from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import QLabel
from gui.desktop_ui.wrappers import QTable
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class UsersSelectionDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "SubjectSelectionDialog",
            "type": "nx::vms::client::desktop::ui::SubjectSelectionDialog",
            "visible": 1,
            })
        self._hid = hid

    def _get_users_table(self):
        table = self._dialog.find_child({
            "type": "nx::vms::client::desktop::TreeView",
            "unnamed": 1,
            "visible": 1,
            })
        return QTable(self._hid, table, ['user_name', 'selection_box'])

    def get_groups_table(self):
        table = self._dialog.find_child({
            "name": "groupsTreeView",
            "type": "nx::vms::client::desktop::TreeView",
            "visible": 1,
            })
        return QTable(self._hid, table, ['user_name', 'selection_box'])

    def get_cloud_users_table(self):
        table = self._dialog.find_child({
            "name": "usersTreeView",
            "type": "nx::vms::client::desktop::TreeView",
            "visible": 1,
            })
        return QTable(self._hid, table, ['user_name', 'group_name', 'selection_box'])

    def select_all_users(self):
        _logger.info('%r: Select All Users', self)
        table = self._get_users_table()
        row = table.find_row(user_name="All Users")
        if not row.cell('selection_box').is_checked():
            row.leftmost_cell().click()

    def select_groups(self, *group_names):
        _logger.info('%r: Select groups: %s', self, group_names)
        table = self.get_groups_table()
        for group_name in group_names:
            row = table.find_row(user_name=group_name)
            if not row.cell('selection_box').is_checked():
                row.leftmost_cell().click()

    def select_cloud_user(self, cloud_user_email):
        _logger.info('%r: Select Cloud user: %s', self, cloud_user_email)
        table = self.get_cloud_users_table()
        email_validation_regex = re.compile(r"^[a-z0-9]+[\._+]?[a-z0-9]+@\w+[.]\w+$")
        if re.match(email_validation_regex, cloud_user_email) is None:
            raise RuntimeError(
                f"User {cloud_user_email} is not a valid Cloud user name. Expected format is email")
        row = table.find_row(user_name=cloud_user_email)
        if not row.cell('selection_box').is_checked():
            row.leftmost_cell().click()

    def close(self):
        _logger.info('%r: Save and close', self)
        ok_button = self._dialog.find_child({
            "text": "OK",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)
        self._dialog.wait_until_closed(10)

    def uncheck_all_users_and_roles(self):
        _logger.info('%r: Uncheck all user and roles', self)
        self._get_users_table().uncheck_all_rows()
        self.get_groups_table().uncheck_all_rows()
        table = self.get_cloud_users_table()
        if table.is_accessible_timeout(0.5):
            table.uncheck_all_rows()
        else:
            _logger.info(
                '%r: No cloud table has appeared. Probably system is not connected to cloud', self)

    def get_alert(self) -> str:
        alert_label = self._dialog.find_child({
            "name": "alertBar",
            "type": "QLabel",
            "visible": 1,
            })
        return QLabel(alert_label).get_text()

    def wait_until_appears(self) -> 'UsersSelectionDialog':
        self._dialog.wait_until_appears()
        return self
