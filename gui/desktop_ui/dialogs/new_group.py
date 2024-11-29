# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.dialogs.group_settings import ResourcesTab
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QmlTabWidget
from gui.desktop_ui.wrappers import TextField
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class NewGroupDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._window = BaseWindow(api=api, locator_or_obj={
            'visible': True,
            'name': 'groupCreateDialog',
            })
        self._hid = hid
        self._api = api

    def set_name(self, name: str):
        _logger.info('%r: Set group name to %s', self, name)
        self._get_name_text_field().type_text(name)

    def set_description(self, description: str):
        _logger.info('%r: Set group description to %s', self, description)
        description_line_edit = TextField(self._hid, self._window.find_child({'id': 'descriptionTextArea'}))
        description_line_edit.type_text(description)

    def create_new_group(self, name: str, description: str):
        self.set_name(name)
        self.set_description(description)
        self._save_and_close()

    def _save_and_close(self):
        _logger.info('%r: Save and close', self)
        self._hid.mouse_left_click_on_object(self._get_add_button())

    def wait_until_appears(self, timeout: float = 3):
        self._window.wait_for_accessible(timeout)

    def get_warning_text(self) -> str:
        widget = self._window.find_child({'id': 'warningMessage', 'visible': True})
        return widget.get_text()

    def close_by_cancel(self):
        _logger.info('%r: Close by Cancel button', self)
        cancel_button = self._get_button_box().find_child({
            'visible': True,
            'type': 'Button',
            'text': 'Cancel',
            })
        self._hid.mouse_left_click_on_object(cancel_button)

    def _get_button_box(self) -> Widget:
        return self._window.find_child({
            'id': 'buttonBox',
            'visible': True,
            })

    def _get_name_text_field(self) -> TextField:
        return TextField(self._hid, self._window.find_child({'id': 'groupNameTextField'}))

    def clear_name_field(self):
        text_field = self._get_name_text_field()
        self._hid.mouse_left_click_on_object(text_field)
        self._hid.keyboard_hotkeys('Ctrl', 'A')
        self._hid.keyboard_hotkeys('Backspace')

    def _get_add_button(self) -> Button:
        button = self._get_button_box().find_child({
            'visible': True,
            'type': 'Button',
            'text': 'Add Group',
            })
        return Button(button)

    def click_add_group_button(self):
        _logger.info('%r: Click Add Group button', self)
        self._hid.mouse_left_click_on_object(self._get_add_button())

    def _select_tab(self, tab_name: str):
        _logger.info('%r: Select tab: %s', self, tab_name)
        tab_widget = self._window.find_child({
            'id': 'tabControl',
            })
        tab = QmlTabWidget(tab_widget).find_tab(tab_name)
        self._hid.mouse_left_click_on_object(tab)

    def get_resources_tab(self) -> 'ResourcesTab':
        self._select_tab('Resources')
        return ResourcesTab(self._window, self._api, self._hid)
