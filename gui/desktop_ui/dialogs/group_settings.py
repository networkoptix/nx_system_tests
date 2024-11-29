# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
from typing import Collection
from typing import Mapping
from typing import Sequence

from gui.desktop_ui.screen import ScreenRectangle
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.widget import WidgetIsAccessible
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import EditableLabel
from gui.desktop_ui.wrappers import QmlTabWidget
from gui.desktop_ui.wrappers import TextField
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class GroupSettingsDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._window = BaseWindow(api=api, locator_or_obj={
            'name': 'groupEditDialog',
            'objectName': 'groupEditDialog',
            'visible': True,
            })

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}>'

    def wait_until_appears(self, timeout: float = 3):
        self._window.wait_until_appears(timeout)

    def _select_tab(self, tab_name: str):
        _logger.info('%r: Select tab: %s', self, tab_name)
        tab_widget = self._window.find_child({
            'id': 'tabControl',
            })
        tab = QmlTabWidget(tab_widget).find_tab(tab_name)
        self._hid.mouse_left_click_on_object(tab)

    def get_general_tab(self) -> '_GeneralTab':
        self._select_tab('General')
        tab = _GeneralTab(self._window, self._hid)
        tab.wait_for_accessible()
        return tab

    def get_members_tab(self) -> '_MembersTab':
        self._select_tab('Members')
        tab = _MembersTab(self._window, self._hid)
        tab.wait_for_accessible()
        return tab

    def get_groups_tab(self) -> '_GroupsTab':
        self._select_tab('Groups')
        tab = _GroupsTab(self._window, self._hid)
        tab.wait_for_accessible()
        return tab

    def get_resources_tab(self) -> 'ResourcesTab':
        self._select_tab('Resources')
        return ResourcesTab(self._window, self._api, self._hid)

    def _get_button(self, button_text: str) -> Button:
        button_box = self._window.find_child({'id': 'buttonBox'})
        widget = button_box.find_child({
            'visible': True,
            'type': 'Button',
            'text': button_text,
            })
        return Button(widget)

    def save_and_close(self):
        _logger.info('%r: Save and close', self)
        ok_button = self._get_button('OK')
        self._hid.mouse_left_click_on_object(ok_button)
        self._window.wait_for_inaccessible()

    def click_apply_button(self):
        _logger.info('%r: Click Apply button', self)
        apply_button = self._get_button('Apply')
        self._hid.mouse_left_click_on_object(apply_button)

    def click_cancel_button(self):
        _logger.info("%r: click Cancel button", self)
        button = self._get_button('Cancel')
        self._hid.mouse_left_click_on_object(button)
        try:
            self._window.wait_for_inaccessible()
        except WidgetIsAccessible:
            _logger.warning(
                "Sometimes (about 1 in every 200-300 runs), clicking on the Cancel button does "
                "not work. Try again")
            self._hid.mouse_left_click_on_object(button)
            self._window.wait_for_inaccessible()


class _GeneralTab:

    def __init__(self, window: BaseWindow, hid: HID):
        self._hid = hid
        self._tab = window.find_child(
            {'id': 'generalSettings', 'type': 'GroupGeneralTab', 'visible': True})

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self._tab!r}>'

    def wait_for_accessible(self) -> True:
        self._tab.wait_for_accessible()

    def set_new_name(self, new_name: str):
        _logger.info('%r: Set new group name: %s', self, new_name)
        text_field = EditableLabel(self._hid, self._tab.find_child({
            'id': 'groupNameTextField',
            'visible': True,
            }))
        text_field.type_text(new_name)

    def set_new_description(self, new_description: str):
        _logger.info('%r: Set new description: %s', self, new_description)
        description_line_edit = TextField(self._hid, self._tab.find_child({
            'id': 'descriptionTextArea'}))
        description_line_edit.type_text(new_description)

    def start_removing(self):
        _logger.info('%r: Start removing group', self)
        delete_button = Button(self._tab.find_child({
            'id': 'buttonText',
            'text': 'Delete',
            'visible': True,
            }))
        self._hid.mouse_left_click_on_object(delete_button)

    def get_permission_groups(self) -> Sequence[str]:
        group_names = []
        for group_widget in self._get_group_widgets():
            group_text_widget = group_widget.find_child({'type': 'QQuickText', 'visible': True})
            group_names.append(group_text_widget.get_text())
        return group_names

    def _get_group_widgets(self) -> Sequence[Widget]:
        """Maintain different versions of the client."""
        # VMS 6.0.
        rows = self._tab.find_children({'id': 'groupRow', 'visible': True})
        if len(rows) == 0:
            # VMS 6.1 and above.
            rows = self._tab.find_children({
                'type': 'MultiSelectionFieldItem',
                'visible': True,
                })
        return rows

    def _get_group_widget(self, group_name: str) -> Widget:
        for group_widget in self._get_group_widgets():
            group_text_widget = group_widget.find_child({'type': 'QQuickText', 'visible': True})
            if group_text_widget.get_text() == group_name:
                return group_widget
        raise RuntimeError(f'Group {group_name!r} not found')

    def exclude_group(self, group_name: str):
        _logger.info('%r: Exclude group "%s"', self, group_name)
        group_widget = self._get_group_widget(group_name)
        cross_icon = group_widget.find_child({
            'visible': True,
            'source': re.compile('cross_input.svg'),
            })
        self._hid.mouse_left_click(cross_icon.bounds().center())

    def is_possible_to_exclude_group(self, group_name: str) -> bool:
        group_widget = self._get_group_widget(group_name)
        elements = group_widget.find_children({
            'visible': True,
            'source': re.compile('cross_input.svg'),
            })
        return elements != []


class _MembersTab:

    def __init__(self, window: BaseWindow, hid: HID):
        self._hid = hid
        self._tab = window.find_child(
            {'id': 'membersSettings', 'type': 'GroupMembersTab', 'visible': True})

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self._tab!r}>'

    def wait_for_accessible(self) -> True:
        self._tab.wait_for_accessible()

    def add_user(self, username: str):
        _logger.info('%r: Add user "%s" to group', self, username)
        item = self._tab.find_child({
            'type': 'SelectableGroupItem',
            'visible': True,
            'text': username,
            })
        self._hid.mouse_left_click_on_object(item)

    def get_selectable_group_members(self) -> Sequence[str]:
        groups = self._tab.find_children({
            'type': 'SelectableGroupItem',
            'visible': True,
            })
        group_names = []
        for group in groups:
            group_names.append(group.get_text())
        return group_names


class _GroupsTab:

    def __init__(self, window: BaseWindow, hid: HID):
        self._hid = hid
        self._tab = window.find_child(
            {'id': 'groupsSettings', 'type': 'ParentGroupsTab', 'visible': True})

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self._tab!r}>'

    def wait_for_accessible(self) -> True:
        self._tab.wait_for_accessible()

    def select_group(self, group_name: str):
        _logger.info('%r: Select group "%s"', self, group_name)
        item = self._get_selectable_group(group_name)
        if item.wait_property('selected'):
            raise RuntimeError(f'Groups {group_name!r} is already selected')
        self._hid.mouse_left_click_on_object(item)

    def unselect_group(self, group_name: str):
        _logger.info('%r: Select group "%s"', self, group_name)
        # In this dialog, elements may become invalid. Try retrieving the group again.
        for _ in range(2):
            item = self._get_selectable_group(group_name)
            selected_value = item.wait_property('selected', timeout=1)
            if selected_value is not None:
                break
        else:
            raise RuntimeError(
                f"Cannot determine the value of the 'selected' property for the group {group_name!r}")
        if not selected_value:
            raise RuntimeError(f"Groups {group_name!r} is already unselected")
        self._hid.mouse_left_click_on_object(item)

    def _get_selectable_group(self, group_name: str) -> Widget:
        group_widget = self._tab.find_child({
            'id': 'editableItem',
            'visible': True,
            'text': group_name,
            })
        return group_widget

    def _get_group_tree(self) -> Widget:
        return self._tab.find_child({'id': 'selectedGroupsListView', 'visible': True})

    def get_existing_group_names(self) -> Sequence[str]:
        group_names = []
        group_widgets = self._get_group_tree().find_children({
            'visible': True,
            'id': 'groupTreeHeader',
            })
        for group in group_widgets:
            # Remove non-breaking space from text result.
            group_names.append(group.get_text().replace('&nbsp;', ' '))
        return group_names

    def selected_groups_count(self) -> int:
        return len(self.list_groups(selected=True))

    def list_groups(self, selected: bool) -> Collection[str]:
        # In this dialog, elements may become invalid. Try retrieving group names again.
        for _ in range(2):
            group_items = self._tab.find_children(
                {'id': 'editableItem', 'visible': True, 'selected': selected})
            group_names = [item.wait_property('text', timeout=1) for item in group_items]
            if None not in group_names:
                return group_names
        else:
            raise RuntimeError("Cannot determine group names")

    def has_existing_groups(self) -> bool:
        return self._get_group_tree().is_visible()

    def get_main_placeholder_text(self) -> str:
        text_widget = self._tab.find_child({
            'visible': True,
            'id': 'placeholderMainText',
            })
        return text_widget.get_text()

    def get_additional_placeholder_text(self) -> str:
        text_widget = self._tab.find_child({
            'visible': True,
            'id': 'placeholderAdditionalText',
            })
        return text_widget.get_text()


# TODO: Improve the User Management widget structure for better hierarchy.
#  The Resource tab should be consistent between the New Group dialog and the Edit Group dialog.
class ResourcesTab:

    def __init__(self, window: BaseWindow, api: TestKit, hid: HID):
        self._window = window
        self._api = api
        self._hid = hid

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}>'

    def _get_permission_settings(self) -> '_PermissionSettings':
        widget = self._window.find_child({'id': 'permissionSettings', 'visible': True})
        return _PermissionSettings(widget, self._hid)

    def get_resource(self, resource_name: str) -> '_ResourceRow':
        settings = self._get_permission_settings()
        return settings.get_resource_row(resource_name)

    def get_tooltip_text(self) -> str:
        tooltip = Widget(
            self._api, {
                'type': 'QQuickText',
                'text': re.compile('permission'),
                'visible': True,
                })
        return tooltip.get_text()

    def get_resources_with_active_permissions(self) -> Collection[str]:
        rows = self._get_permission_settings().get_resource_rows()
        resources_with_active_permissions = []
        for resource, row in rows.items():
            permissions = row.get_active_permissions()
            _logger.info(
                '%r: Group permissions for resource "%s" are: %s',
                self, resource, permissions)
            if len(permissions) > 0:
                resources_with_active_permissions.append(resource)
        return resources_with_active_permissions


class _PermissionSettings:

    def __init__(self, settings_widget: Widget, hid: HID):
        self._widget = settings_widget
        self._hid = hid

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self._widget!r}>'

    def _get_header(self) -> Widget:
        return self._widget.find_child({'id': 'accessRightsHeader', 'visible': True})

    def _get_permission_header_names(self) -> Sequence[str]:
        items = self._get_header().find_children({
            'id': 'accessRightItem',
            'visible': True,
            'type': 'AccessRightsHeaderItem',
            })
        permissions = []
        for item in items:
            permissions.append(item.get_text())
        return permissions

    def get_resource_rows(self) -> Mapping[str, '_ResourceRow']:
        rows = self._widget.find_children({
            'id': 'item',
            'visible': True,
            'type': 'ResourceAccessDelegate',
            })
        permissions = self._get_permission_header_names()
        rows = [_ResourceRow(row, self._hid, permissions) for row in rows]
        return {row.name(): row for row in rows}

    def get_resource_row(self, resource: str) -> '_ResourceRow':
        return self.get_resource_rows()[resource]


class _ResourceRow:

    def __init__(self, widget: Widget, hid: HID, permissions: Sequence[str]):
        self._widget = widget
        self._hid = hid
        self._headers = permissions

    def _cells(self) -> Sequence['_PermissionCell']:
        cells = self._widget.find_children({'id': 'cell', 'visible': True})
        return [_PermissionCell(cell, self._hid) for cell in cells]

    def name(self) -> str:
        name_widget = self._widget.find_child({'id': 'name', 'visible': True})
        # Remove non-breaking space from text result.
        return name_widget.get_text().replace('amp;', '')

    def get_active_permissions(self) -> Sequence[str]:
        cells = self._cells()
        active_permissions = []
        for i in range(len(cells)):
            if cells[i].has_access_icon():
                active_permissions.append(self._headers[i])
        return active_permissions

    def permission(self, permission: str) -> '_PermissionCell':
        index = self._headers.index(permission)
        return self._cells()[index]


class _PermissionCell:

    def __init__(self, widget: Widget, hid: HID):
        self._widget = widget
        self._hid = hid

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}: {self._widget!r}>'

    def has_access_icon(self) -> bool:
        icon_source = self._get_icon_source()
        valid_icon_names = ['group.svg', 'own.svg', 'success.svg']
        if icon_source is None:
            return False
        elif any([icon_name in icon_source for icon_name in valid_icon_names]):
            return True
        else:
            raise RuntimeError(f'Unknown permission status icon: {icon_source}')

    def _get_icon_source(self) -> str:
        icon = self._widget.find_child({
            'visible': True,
            'source': re.compile(r'.+'),
            })
        if icon.is_accessible_timeout(0):
            source = icon.wait_property('source')
            _logger.info('%r: Found cell with icon source %s', self, source)
            return source

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()
