# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from collections.abc import Collection
from typing import Sequence

from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import EditableLabel
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QmlListView
from gui.desktop_ui.wrappers import QmlTabWidget
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class UserSettingsDialog:
    """QML-based User Settings Dialog."""

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._window = BaseWindow(api=api, locator_or_obj={
            'name': 'userEditDialog',
            'objectName': 'userEditDialog',
            'visible': True,
            })

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}>'

    def wait_until_appears(self, timeout: float = 3):
        self._window.wait_until_appears(timeout=timeout)

    def _select_tab(self, tab_name):
        _logger.info('%r: Select tab: %s', self, tab_name)
        tab_widget = QmlTabWidget(self._window.find_child({
            'id': 'tabControl',
            }))
        tab = tab_widget.find_tab(tab_name)
        self._hid.mouse_left_click_on_object(tab)

    def select_general_tab(self) -> '_GeneralTab':
        self._select_tab('General')
        tab = _GeneralTab(self._window, self._api, self._hid)
        tab.wait_for_accessible()
        return tab

    def select_groups_tab(self) -> '_GroupsTab':
        self._select_tab('Groups')
        tab = _GroupsTab(self._window, self._api, self._hid)
        tab.wait_for_accessible()
        return tab

    def save_and_close(self):
        button_box = self._window.find_child({'id': 'buttonBox'})
        save_button = button_box.find_child({
            'visible': True,
            'type': 'Button',
            'text': 'OK',
            })
        self._hid.mouse_left_click_on_object(save_button)
        self._window.wait_for_inaccessible()


class _GeneralTab:

    def __init__(self, window: BaseWindow, api: TestKit, hid: HID):
        self._window = window
        self._api = api
        self._hid = hid
        self._tab = window.find_child(
            {'id': 'generalSettings', 'type': 'UserGeneralTab', 'visible': True})

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self._tab!r}>'

    def wait_for_accessible(self) -> True:
        self._tab.wait_for_accessible()

    def set_login(self, value):
        _logger.info('%r: Set login %s', self, value)
        login_line_edit = EditableLabel(self._hid, self._tab.find_child({
            'type': 'EditableLabel',
            'visible': True,
            }))
        login_line_edit.type_text(value)

    def set_full_name(self, full_name: str):
        _logger.info('%r: Set full name %s', self, full_name)
        name_line_edit = QLineEdit(self._hid, self._tab.find_child({
            'id': 'userFullNameTextField',
            'type': 'TextField',
            'visible': True,
            }))
        name_line_edit.type_text(full_name)

    def set_email(self, email: str):
        _logger.info('%r: Set Email %s', self, email)
        text_field = self._tab.find_child({
            'id': 'userEmailTextField',
            'type': 'TextFieldWithValidator',
            })
        email_line_edit = QLineEdit(self._hid, text_field.find_child({
            'type': 'TextField',
            'visible': True,
            }))
        email_line_edit.type_text(email)

    def set_group(self, group_name: str):
        _logger.info('%r: Set group %s', self, group_name)
        self._hid.mouse_left_click_on_object(self._get_groups_combobox())
        list_view = self._get_groups_list_view()
        group = list_view.get_options_with_names()[group_name]
        if not list_view.bounds().contains_rectangle(group.bounds()):
            self._scroll_down_to_group(group, group_name, list_view)
        self._hid.mouse_left_click_on_object(group)

    def start_removing(self):
        _logger.info('%r: Start removing user', self)
        delete_button = Button(self._tab.find_child({
            'id': 'buttonText',
            'text': 'Delete',
            'visible': True,
            }))
        self._hid.mouse_left_click_on_object(delete_button)

    def _scroll_down_to_group(
            self,
            group_widget: Widget,
            group_name: str,
            list_view: QmlListView,
            ):
        _logger.info('%r: Scroll down to group %s', self, group_name)
        for _ in range(5):
            self._hid.mouse_scroll(list_view.bounds().center(), scroll_delta=-150)
            if list_view.bounds().contains_rectangle(group_widget.bounds()):
                return
            _logger.info('%r: Group %s is hidden. Repeat mouse scroll action', self, group_name)
        raise RuntimeError(f'Group {group_name!r} is unreachable by scroll')

    def _get_groups_list_view(self):
        """Maintain different versions of the client."""
        # The dropdown list with group names belongs to the window, not the tab.
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

    def _get_groups_combobox(self) -> Widget:
        return self._tab.find_child({
            "visible": 1,
            'id': 'groupsComboBox',
            })

    def get_login(self):
        return self._tab.wait_property('login')

    def get_group(self):
        # Should be reworked according new testcases.
        first_group = self._get_groups()[0]
        return first_group.get_text()

    def _get_groups(self):
        """Maintain different versions of the client."""
        # VMS 6.0.
        rows = self._tab.find_children({
            'container': {'id': 'groupRow'},
            'type': 'QQuickText',
            'visible': True,
            })
        if len(rows) == 0:
            # VMS 6.1 and above.
            rows = self._tab.find_children({
                'container': {'id': 'groupsComboBox'},
                'type': 'QQuickText',
                'visible': True,
                })
        return rows

    def get_selected_groups_names(self) -> Sequence[str]:
        groups = []
        for group_widget in self._get_groups():
            groups.append(group_widget.get_text())
        return groups


class _GroupsTab:

    def __init__(self, window: BaseWindow, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._tab = window.find_child(
            {'id': 'groupsSettings', 'type': 'ParentGroupsTab', 'visible': True})

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self._tab!r}>'

    def wait_for_accessible(self) -> True:
        self._tab.wait_for_accessible()

    def toggle_group(self, group_name: str):
        _logger.info('%r: Toggle group %s', self, group_name)
        item = self._tab.find_child({
            'type': 'MembershipEditableItem',
            'visible': True,
            'text': group_name,
            })
        self._hid.mouse_left_click_on_object(item)

    def list_groups(self, selected: bool) -> Collection[str]:
        group_items = self._tab.find_children(
            {'type': 'MembershipEditableItem', 'selected': selected, 'visible': True})
        group_names = [item.wait_property('text', timeout=1) for item in group_items]
        return group_names

    def get_existing_group_names(self) -> Collection[str]:
        group_tree = self._tab.find_child({'id': 'selectedGroupsListView', 'visible': True})
        group_items = group_tree.find_children({'visible': True, 'id': 'groupTreeHeader'})
        group_names = [item.wait_property('text') for item in group_items]
        return [name.replace('&nbsp;', ' ') for name in group_names]
