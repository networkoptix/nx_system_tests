# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import time
from collections.abc import Collection
from collections.abc import Mapping
from collections.abc import Sequence
from enum import Enum
from typing import Any

from gui.desktop_ui.dialogs.group_settings import GroupSettingsDialog
from gui.desktop_ui.dialogs.ldap_advanced_settings import LDAPAdvancedSettingsDialog
from gui.desktop_ui.dialogs.ldap_connection_settings import LDAPConnectionSettingsDialog
from gui.desktop_ui.dialogs.new_group import NewGroupDialog
from gui.desktop_ui.dialogs.new_user import NewUserDialog
from gui.desktop_ui.dialogs.user_settings import UserSettingsDialog
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QTable
from gui.desktop_ui.wrappers import RowNotFound
from gui.desktop_ui.wrappers import TabWidget
from gui.desktop_ui.wrappers import TextField
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class LDAPConnectionStatus(Enum):
    ONLINE = 'ONLINE'
    OFFLINE = 'OFFLINE'


class UserManagementWidget:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._active_tab = None
        self._system_administration_dialog = BaseWindow(api=self._api, locator_or_obj={
            "name": "QnSystemAdministrationDialog",
            "type": "QnSystemAdministrationDialog",
            "visible": 1,
            "occurrence": 1,
            })

    def _set_tab(self, tab_name: str):
        if self._active_tab is None or self._active_tab != tab_name:
            _logger.info('%r: Set tab %s', self, tab_name)
            tab_widget = self._system_administration_dialog.find_child({
                'visible': True,
                'type': 'QStackedWidget',
                'occurrence': 1,
                })
            tab = TabWidget(tab_widget).find_tab(tab_name)
            self._hid.mouse_left_click_on_object(tab)
            self._active_tab = tab_name

    def _set_users_tab(self) -> '_UsersTab':
        self._set_tab('Users')
        return _UsersTab(self._api, self._hid)

    def get_groups_tab(self) -> '_GroupsTab':
        self._set_tab('Groups')
        return _GroupsTab(self._api, self._hid)

    def has_user(self, username: str) -> bool:
        tab = self._set_users_tab()
        return tab.has_user(username)

    def has_group(self, group_name: str) -> bool:
        tab = self.get_groups_tab()
        return tab.has_group(group_name)

    def get_users_names(self) -> list[str]:
        tab = self._set_users_tab()
        return tab.get_users_names()

    def open_new_user_dialog(self) -> 'NewUserDialog':
        _logger.info('%r: Open New User Dialog', self)
        return self._set_users_tab().open_new_user_dialog()

    def open_new_group_dialog(self) -> 'NewGroupDialog':
        _logger.info('%r: Open New Group Dialog', self)
        return self.get_groups_tab().open_new_group_dialog()

    def open_user_settings(self, login: str) -> 'UserSettingsDialog':
        _logger.info('%r: Open User Settings Dialog for group %s', self, login)
        return self._set_users_tab().open_user_settings(login)

    def open_group_settings(self, group_name: str) -> 'GroupSettingsDialog':
        _logger.info('%r: Open Group Settings Dialog for group %s', self, group_name)
        return self.get_groups_tab().open_group_setting_dialog(group_name)

    def get_user_data_by_name(self, username: str) -> Mapping[str, str]:
        return self._set_users_tab().get_user_data_by_name(username)

    def get_group_data_by_name(self, group_name: str) -> Mapping[str, str]:
        return self.get_groups_tab().get_group_data_by_name(group_name)

    def get_groups(self, login: str) -> str:
        return self._set_users_tab().get_groups(login)

    def select_user(self, username: str):
        self._set_users_tab().select_user(username)

    def start_deleting_selected_rows(self):
        delete_button = self._get_delete_button()
        self._hid.mouse_left_click_on_object(delete_button)

    def _get_delete_button(self) -> Button:
        bar = self._system_administration_dialog.find_child({
            'type': 'nx::vms::client::desktop::ControlBar',
            'visible': True,
            })
        return Button(bar.find_child({'type': 'QPushButton', 'text': 'Delete'}))

    def select_group(self, group_name: str):
        self.get_groups_tab().select_group(group_name)

    def get_groups_count(self) -> int:
        return self.get_groups_tab().get_groups_count()

    def add_cloud_user(self, email: str, groups: Collection[str]):
        new_user_dialog = self.open_new_user_dialog()
        new_user_dialog.wait_until_appears()
        new_user_dialog.general_tab().set_email(email)
        for group in groups:
            new_user_dialog.general_tab().set_group(group)
        new_user_dialog.save()

    def get_ldap_tab(self) -> '_LDAPTab':
        self._set_tab('LDAP')
        return _LDAPTab(self._api, self._hid)

    def get_groups_names(self) -> Collection[str]:
        tab = self.get_groups_tab()
        return tab.get_groups_names()


class _BaseTab:

    def __init__(
            self,
            tab_name: str,
            columns: Collection[str],
            api: TestKit,
            hid: HID,
            ):
        self._tab_name = tab_name
        self._columns = columns
        self._api = api
        self._hid = hid

    def _get_table(self):
        table_object = Widget(self._api, {
            'name': f'{self._tab_name}Table',
            'type': 'nx::vms::client::desktop::TreeView',
            'visible': 1,
            })
        return QTable(self._hid, table_object, self._columns)


class _UsersTab(_BaseTab):

    def __init__(self, api: TestKit, hid: HID):
        users_columns = [None, None, None, 'login', 'name', 'email', 'groups', 'custom']
        super().__init__("users", users_columns, api, hid)

    def open_new_user_dialog(self) -> 'NewUserDialog':
        new_user_button = Button(Widget(self._api, {
            "name": "createUserButton",
            "type": "QPushButton",
            "visible": 1,
            }))
        self._hid.mouse_left_click_on_object(new_user_button)
        dialog = NewUserDialog(self._api, self._hid)
        dialog.wait_until_appears()
        return dialog

    def get_user_data_by_name(self, username: str) -> Mapping[str, str]:
        row = self._get_table().find_row(login=username)
        return row.data()

    def open_user_settings(self, login: str) -> 'UserSettingsDialog':
        cell = self._get_table().find_row(login=login).cell(column_name='login')
        cell.click()
        dialog = UserSettingsDialog(self._api, self._hid)
        dialog.wait_until_appears()
        return dialog

    def has_user(self, username: str) -> bool:
        try:
            self._get_table().find_row(login=username)
            return True
        except RowNotFound:
            return False

    def get_users_names(self) -> list[str]:
        return self._get_table().column_values('login')

    def get_groups(self, login: str) -> str:
        row = self._get_table().find_row(login=login)
        groups = row.cell('groups').get_display_text()
        return groups

    def select_user(self, username: str):
        row = self._get_table().find_row(login=username)
        self._hid.mouse_left_click_on_object(row.leftmost_cell())


class _GroupsTab(_BaseTab):

    def __init__(self, api: TestKit, hid: HID):
        groups_columns = [None, None, None, 'name', 'description', 'member_of', 'custom']
        super().__init__("groups", groups_columns, api, hid)

    def open_new_group_dialog(self) -> 'NewGroupDialog':
        new_group_button = Button(Widget(self._api, {
            'name': 'createGroupButton',
            'type': 'QPushButton',
            'visible': 1,
            }))
        self._hid.mouse_left_click_on_object(new_group_button)
        dialog = NewGroupDialog(self._api, self._hid)
        dialog.wait_until_appears()
        return dialog

    def get_group_data_by_name(self, group_name: str) -> Mapping[str, str]:
        row = self._get_table().find_row(name=group_name)
        return row.data()

    def has_group(self, group_name: str) -> bool:
        try:
            self._get_table().find_row(name=group_name)
            return True
        except RowNotFound:
            return False

    def open_group_setting_dialog(self, group_name: str) -> 'GroupSettingsDialog':
        cell = self._get_table().find_row(name=group_name).cell(column_name='name')
        cell.click()
        dialog = GroupSettingsDialog(self._api, self._hid)
        dialog.wait_until_appears()
        return dialog

    def select_group(self, group_name: str):
        row = self._get_table().find_row(name=group_name)
        self._hid.mouse_left_click_on_object(row.leftmost_cell())

    def get_groups_count(self) -> int:
        return len(self._get_table().all_rows())

    def get_groups_names(self) -> Collection[str]:
        return self._get_table().column_values('name')


class _LDAPTab:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._widget = Widget(self._api, {'visible': True, 'name': 'tabWidget'})
        self._hid = hid

    def open_configure_dialog(self) -> 'LDAPConnectionSettingsDialog':
        _logger.info('%r: Open configure LDAP dialog', self)
        button = self.get_configure_button()
        self._hid.mouse_left_click(button.center())
        return LDAPConnectionSettingsDialog(self._api, self._hid)

    def open_advanced_settings(self) -> LDAPAdvancedSettingsDialog:
        _logger.info('%r: Open Advanced Settings dialog', self)
        button = self._widget.find_child(
            {'text': 'Advanced Settings', 'visible': 1, 'type': 'TextButton'})
        self._hid.mouse_left_click(button.center())
        return LDAPAdvancedSettingsDialog(self._api, self._hid)

    def has_message(self, pattern: re.Pattern) -> bool:
        elements = self._widget.find_children({'visible': True, 'text': pattern})
        return len(elements) > 0

    def add_search_base(self, name: str, base_dn: str, filter_string: str):
        _logger.info("%r: Open 'Add search base' dialog", self)
        button = self._widget.find_child(
            {"text": "+ Add", "visible": 1, 'type': 'TextButton'})
        self._hid.mouse_left_click(button.center())
        add_search_dialog = _LdapAddSearchBaseDialog(self._api, self._hid)
        add_search_dialog.fill_name(name)
        add_search_dialog.fill_base_dn(base_dn)
        add_search_dialog.fill_filter(filter_string)
        add_search_dialog.click_ok()

    def get_users_and_groups_count(self) -> tuple[int, int]:
        locator = {
            'container': {
                'type': 'QQuickGridLayout',
                'visible': True,
                },
            'visible': True,
            'type': 'QQuickText',
            'text': re.compile(r'-|(\d+$)'),
            }
        elements = self._widget.find_children(locator)
        if len(elements) < 2:
            raise SynchronisationInProgress()
        try:
            count_users = int(elements[0].get_text())
        except ValueError:
            raise SynchronisationIsNotPerformed()
        try:
            count_groups = int(elements[1].get_text())
        except ValueError:
            raise SynchronisationIsNotPerformed()
        return count_users, count_groups

    def get_last_sync_time_min(self) -> int:
        pattern = re.compile(r'(just now)|((?P<min>\d*) minute(.?) ago)')
        locator = {
            'container': {
                'type': 'QQuickGridLayout',
                'visible': True,
                },
            'visible': True,
            'enabled': True,
            'type': 'QQuickText',
            'text': pattern,
            }
        elements = self._widget.find_children(locator)
        if not elements:
            raise SynchronisationIsNotPerformed()
        text = elements[0].get_text()
        match_result = pattern.match(text)
        last_time_min = match_result.group('min') or 0
        return int(last_time_min)

    def wait_until_synchronization_completed(self):
        timeout = 10
        finished_at = time.monotonic() + timeout
        while True:
            try:
                self.get_users_and_groups_count()
                self.get_last_sync_time_min()
            except (SynchronisationInProgress, SynchronisationIsNotPerformed):
                _logger.debug("LDAP synchronization is not performed yet")
                if time.monotonic() > finished_at:
                    raise RuntimeError(f"LDAP synchronization has not started after {timeout} seconds")
                time.sleep(1)
            else:
                break

    def get_connection_status(self) -> LDAPConnectionStatus:
        widget = self._widget.find_child(
            {'id': 'statusTagText', 'type': 'QQuickText', 'visible': True, 'enabled': True})
        status_text = widget.get_text()
        return LDAPConnectionStatus(status_text)

    def is_address_displayed(self, address: Any) -> bool:
        elements = self._widget.find_children({'text': str(address), 'visible': True, 'enabled': True})
        return len(elements) == 1

    def list_message_banners(self) -> Sequence[str]:
        elements = self._widget.find_children({'type': 'DialogBanner', 'visible': True, 'enabled': True})
        return [element.get_text() for element in elements]

    def get_configure_button(self) -> Button:
        button_locator = {'visible': True, 'enabled': True, 'text': 'Configure', 'type': 'Button'}
        return Button(self._widget.find_child(button_locator))

    def open_disconnect_message_box(self) -> MessageBox:
        _logger.info("%r: Open 'Disconnect' message box", self)
        button_locator = {
            'visible': True,
            'enabled': True,
            'id': 'resetConnectionSettings',
            'type': 'TextButton',
            }
        button = Button(self._widget.find_child(button_locator))
        self._hid.mouse_left_click(button.center())
        return MessageBox(self._api, self._hid)


class _LdapAddSearchBaseDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._widget = Widget(api, {'type': 'FilterDialog', 'visible': True})
        self._hid = hid

    def fill_name(self, value: str):
        _logger.info("%r: Fill name: '%s'", self, value)
        text_field = TextField(self._hid, self._widget.find_child({
            'id': 'nameField',
            'type': 'CenteredField',
            'visible': True,
            }))
        self._hid.mouse_left_click(text_field.bounds().center().up(10))
        self._hid.write_text(value)

    def fill_base_dn(self, value: str):
        _logger.info("%r: Fill Base DN: '%s'", self, value)
        text_field = TextField(self._hid, self._widget.find_child({
            'id': 'baseDnField',
            'type': 'CenteredField',
            'visible': True,
            }))
        self._hid.mouse_left_click(text_field.bounds().center().up(10))
        self._hid.write_text(value)

    def fill_filter(self, value: str):
        _logger.info("%r: Fill filter: '%s'", self, value)
        text_field = TextField(self._hid, self._widget.find_child({
            'id': 'filterField',
            'type': 'CenteredField',
            'visible': True,
            }))
        self._hid.mouse_left_click(text_field.bounds().center().up(10))
        self._hid.write_text(value)

    def click_ok(self):
        _logger.info('%r: Click OK button', self)
        button = Button(self._widget.find_child({
            'text': 'OK',
            'type': 'Button',
            'visible': True,
            }))
        self._hid.mouse_left_click(button.center())


class SynchronisationIssue(Exception):
    pass


class SynchronisationInProgress(SynchronisationIssue):
    pass


class SynchronisationIsNotPerformed(SynchronisationIssue):
    pass
