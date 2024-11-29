# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from typing import Sequence

from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QmlListView
from gui.desktop_ui.wrappers import QmlTabWidget
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class NewUserDialog:
    """System Administration dialog -> Users tab -> New User...

    Maintain QML-based New User Dialog.
    See more: https://networkoptix.atlassian.net/browse/VMS-16938
    """

    _qmlNewUserDialog_locator = {
        'name': 'userCreateDialog',
        'objectName': 'userCreateDialog',
        'visible': True,
        }

    def __init__(self, api: TestKit, hid: HID):
        self._window = BaseWindow(api=api, locator_or_obj=self._qmlNewUserDialog_locator)
        self._hid = hid
        self._general_tab = _GeneralTab(self._window, api, self._hid)
        self._groups_tab = _GroupsTab(self._window, api, self._hid)

    def general_tab(self):
        self._select_tab('General')
        return self._general_tab

    def groups_tab(self):
        self._select_tab('Groups')
        groups_settings = self._window.find_child({'id': 'groupsSettings'})
        groups_settings.wait_for_accessible()
        return self._groups_tab

    def _select_tab(self, tab_name):
        _logger.info('%r: Select tab: %s', self, tab_name)
        tab_widget = self._window.find_child({
            'id': 'tabControl',
            })
        tab = QmlTabWidget(tab_widget).find_tab(tab_name)
        self._hid.mouse_left_click_on_object(tab)

    def _get_save_button(self):
        group_box = self._window.find_child({
            'id': 'buttonBox',
            'visible': True,
            })
        button = group_box.find_child({
            'visible': True,
            'type': 'Button',
            'text': 'Add User',
            })
        return Button(button)

    def _get_cancel_button(self) -> Button:
        group_box = self._window.find_child({
            'id': 'buttonBox',
            'visible': True,
            })
        button = group_box.find_child({
            'visible': True,
            'type': 'Button',
            'text': 'Cancel',
            })
        return Button(button)

    def save(self):
        _logger.info('%r: Save and close', self)
        self._hid.mouse_left_click_on_object(self._get_save_button())
        self._window.wait_for_inaccessible()

    def close_by_cancel_button(self):
        _logger.info('%r: Close by Cancel button', self)
        self._hid.mouse_left_click_on_object(self._get_cancel_button())
        self._window.wait_for_inaccessible()

    def wait_until_appears(self, timeout: float = 3):
        self._window.wait_for_accessible(timeout)


class _GeneralTab:

    def __init__(self, window: BaseWindow, api: TestKit, hid: HID):
        self._window = window
        self._api = api
        self._hid = hid

    def set_login(self, value):
        _logger.info('%r: Set login %s', self, value)
        self._get_login_line_edit().type_text(value)

    def set_email(self, email: str):
        _logger.info('%r: Set email %s', self, email)
        self._get_email_line_edit().type_text(email)

    def set_password(self, value):
        _logger.info('%r: Set password', self)
        self._get_password_line_edit().type_text(value)
        self._get_confirm_password_line_edit().type_text(value)

    def set_group(self, group: str):
        self._hid.mouse_left_click_on_object(self._get_groups_combobox())
        list_view = self._get_groups_list_view()
        options = list_view.get_options_with_names()
        self._hid.mouse_left_click_on_object(options[group])

    def wait_until_group_selected(self, group_name: str):
        combo_box = self._get_groups_combobox()
        group_row_text_label = combo_box.find_child({
            'container': {
                'visible': True,
                'type': 'QQuickRowLayout',
                },
            'type': 'QQuickText',
            'text': group_name,
            })
        group_row_text_label.wait_for_accessible(1)

    def _get_password_line_edit(self):
        text_field = self._window.find_child({
            'id': 'passwordTextField',
            'visible': True,
            })
        field = text_field.find_child({'id': 'textField'})
        return QLineEdit(self._hid, field)

    def _get_confirm_password_line_edit(self):
        text_field = self._window.find_child({
            'id': 'confirmPasswordTextField',
            'visible': True,
            })
        field = text_field.find_child({'id': 'textField'})
        return QLineEdit(self._hid, field)

    def _get_login_line_edit(self):
        text_field = self._window.find_child({
            'id': 'loginTextField',
            'visible': True,
            })
        field = text_field.find_child({'id': 'textField'})
        return QLineEdit(self._hid, field)

    def _get_email_line_edit(self):
        text_field = self._window.find_child({
            'id': 'emailTextField',
            'visible': True,
            })
        field = text_field.find_child({'id': 'textField'})
        return QLineEdit(self._hid, field)

    def _get_groups_combobox(self) -> Widget:
        return self._window.find_child({
            "visible": 1,
            'id': 'groupsComboBox',
            })

    def _get_groups_list_view(self):
        """Maintain different versions of the client."""
        # VMS 6.0.
        list_view = self._window.find_child({
            'visible': True,
            'id': 'groupListView',
            })
        if not list_view.is_accessible_timeout(0.5):
            # VMS 6.1 and above.
            list_view = self._window.find_child({
                'visible': True,
                'id': 'listView',
                })
        return QmlListView(list_view, self._hid)


class _GroupsTab:

    def __init__(self, window: BaseWindow, api: TestKit, hid: HID):
        self._window = window
        self._api = api
        self._hid = hid

    def _set_group(self, value: str):
        _logger.info('%r: Set group %s', self, value)
        group_item = self._window.find_child({
            'type': 'MembershipEditableItem',
            'visible': True,
            'text': value,
            })
        self._hid.mouse_left_click_on_object(group_item)

    def get_selected_group_names(self) -> Sequence[str]:
        _logger.info('%r: Get marked groups', self)
        group_names = []
        for group in self._get_selected_groups():
            group_names.append(group.get_text())
        return group_names

    def _unset_all_groups(self):
        _logger.info('%r: Unset all groups', self)
        selected_groups = self._get_selected_groups()
        for group in selected_groups:
            self._hid.mouse_left_click_on_object(group)

    def set_several_groups(self, groups: Sequence[str]):
        self._unset_all_groups()
        for group in groups:
            self._set_group(group)

    def _get_selected_groups(self) -> Sequence[Widget]:
        return self._window.find_children({
            'type': 'MembershipEditableItem',
            'selected': True,
            'enabled': True,
            'visible': True,
            })

    def get_group_names(self) -> Sequence[str]:
        group_names = []
        for group in self._get_groups():
            group_names.append(group.get_text())
        return group_names

    def _get_groups(self) -> Sequence[Widget]:
        return self._window.find_children({
            'type': 'MembershipEditableItem',
            'enabled': True,
            'visible': True,
            })
