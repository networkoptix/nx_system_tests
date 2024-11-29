# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from typing import Sequence

from gui.desktop_ui.dialogs.upload import CustomUploadDialog
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import Checkbox
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QMenu
from gui.desktop_ui.wrappers import TabWidget
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class LayoutTabBar:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._obj = Widget(api, {
            "type": "QnLayoutTabBar",
            "unnamed": 1,
            "visible": 1,
            })

    def _get_layouts(self) -> Sequence['Widget']:
        return self._obj.find_children({'type': 'TabItem'})

    def layout(self, name) -> Widget:
        _logger.info('%r: Looking for layout with name %s', self, name)
        for layout in self._get_layouts():
            if layout.get_text() == name:
                return layout
        raise _LayoutNotFoundError(f'Layout {name} not found')

    def _wait_for_layout(self, name, timeout: float = 3):
        _logger.info(
            '%r: Wait for layout with name %s appears. Timeout: %s second(s)',
            self, name, timeout)
        start = time.monotonic()
        while True:
            layout = self.layout(name)
            if layout is None:
                _logger.debug('Layout with name %s not found yet', name)
            else:
                return
            if time.monotonic() - start > timeout:
                raise RuntimeError(f'Layout with name {name} does not exist')
            time.sleep(.1)

    def add_new_tab(self):
        _logger.info('%r: Add new tab', self)
        locator = {
            "text": "Layout",
            "type": "nx::vms::client::desktop::ToolButton",
            "unnamed": 1,
            "visible": 1,
            }
        new_tab_button = Widget(self._api, locator)
        if new_tab_button.is_accessible_timeout(0):
            self._hid.mouse_left_click_on_object(new_tab_button)
        else:
            # The locator for VMS 6.1 and above should be changed.
            locator['text'] = "Layout Tab"
            new_tab_button = Widget(self._api, locator)
            self._hid.mouse_left_click_on_object(new_tab_button)

    def create(self, layout_name):
        _logger.info('%r: Create new layout: %s', self, layout_name)
        self.add_new_tab()
        self.save_current_as(layout_name)

    def save(self, layout_name):
        _logger.info('%r: Save layout: %s', self, layout_name)
        self._hid.mouse_left_click_on_object(self.layout(layout_name))
        self._obj.wait_for_accessible()
        self._hid.keyboard_hotkeys('Ctrl', 'S')
        if layout_name[-1] == '*':
            layout_name = layout_name[:-1]
        self._wait_for_layout(layout_name)

    def save_current_as(self, new_name):
        _logger.info('%r: Save current layout: %s', self, new_name)
        self._obj.wait_for_accessible()
        self._hid.keyboard_hotkeys('Ctrl', 'Shift', 'S')
        layout_name_dialog = LayoutNameDialog(self._api, self._hid)
        layout_name_dialog.dialog.wait_for_accessible()
        layout_name_dialog.get_name_field().type_text(new_name)
        self._hid.mouse_left_click_on_object(layout_name_dialog.get_save_button())
        self._wait_for_layout(new_name)

    def close(self, layout_name):
        _logger.info('%r: Close layout: %s', self, layout_name)
        if len(self._get_layouts()) < 2:
            # If only one layout is open it wouldn't close.
            self.add_new_tab()

        self._hid.mouse_left_click_on_object(self.layout(layout_name))
        self._obj.wait_for_accessible()
        self._hid.keyboard_hotkeys('Ctrl', 'W')

    def close_current_layout(self):
        _logger.info('%r: Close current layout', self)
        current_index = TabWidget(self._obj).get_current_index()
        close_button = self._obj.find_child({
            "type": "CloseButton",
            "unnamed": 1,
            "visible": 1,
            "occurrence": current_index + 1,
            })
        self._hid.mouse_left_click_on_object(close_button)
        time.sleep(1)

    def _activate_context_menu_item(self, layout_name, item_name):
        self._hid.mouse_right_click_on_object(self.layout(layout_name))
        menu = QMenu(self._api, self._hid)
        menu.wait_for_accessible()
        menu.activate_items([item_name])

    def is_open(self, layout_name):
        # TODO: add a check that layout not only exists but is also active after SQ-122 is done.
        self._obj.wait_for_object()
        try:
            self.layout(layout_name)
        except _LayoutNotFoundError:
            return False
        return True

    def wait_for_open(self, layout_name, timeout: float = 2):
        _logger.info(
            '%r: Wait for layout with name %s open. Timeout: %s second(s)',
            self, layout_name, timeout)
        start_time = time.monotonic()
        while True:
            if self.is_open(layout_name):
                return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError(f"Layout {layout_name} is not open")
            time.sleep(.5)


class LayoutNameDialog:

    def __init__(self, api: TestKit, hid: HID):
        self.dialog = BaseWindow(api=api, locator_or_obj={
            "name": "LayoutNameDialog",
            "type": "QnLayoutNameDialog",
            "visible": 1,
            })
        self._hid = hid

    def get_name_field(self):
        field = self.dialog.find_child({
            "name": "nameLineEdit",
            "type": "QLineEdit",
            "visible": 1,
            })
        return QLineEdit(self._hid, field)

    def get_save_button(self):
        button = self.dialog.find_child({
            "text": "Save",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        return Button(button)


class LayoutSettings:

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "LayoutSettingsDialog",
            "type": "nx::vms::client::desktop::LayoutSettingsDialog",
            "visible": 1,
            "occurrence": 1,
            })
        self._api = api
        self._hid = hid

    def get_view_button(self):
        button = self._dialog.find_child({
            "name": "viewButton",
            "type": "QPushButton",
            "visible": 1,
            })
        return Button(button)

    def open_background_tab(self):
        _logger.info('%r: Open Background tab', self)
        tab_widget = self._dialog.find_child({
            "name": "tabWidget",
            "type": "QTabWidget",
            "visible": 1,
            })
        tab = TabWidget(tab_widget).find_tab("Background")
        self._hid.mouse_left_click_on_object(tab)

    def _get_browse_button(self):
        button = self._dialog.find_child({
            "name": "selectButton",
            "type": "QPushButton",
            "visible": 1,
            })
        return Button(button)

    def _get_file_field(self):
        field = self._dialog.find_child({
            "name": "fileNameEdit",
            "type": "QLineEdit",
            "visible": 1,
            })
        return QLineEdit(self._hid, field)

    def select_background(self, path):
        _logger.info('%r: Select background: %s', self, path)
        self.open_background_tab()
        self._hid.mouse_left_click_on_object(self._get_browse_button())
        CustomUploadDialog(self._api, self._hid).wait_until_appears().upload_file(str(path), 0)

    def set_background(self, path):
        _logger.info('%r: Set background: %s', self, path)
        self.select_background(path)
        # Set opacity to 100% to simplify matching.
        self.get_opacity_field().type_text('100')
        self.save_settings()
        # New background rendering takes time.
        time.sleep(2)

    def clear_background(self):
        _logger.info('%r: Clear background', self)
        self.open_background_tab()
        clear_button = self._dialog.find_child({
            "name": "clearButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(clear_button)
        self.save_settings()

    def get_width_field(self):
        width_field = self._dialog.find_child({
            "name": "qt_spinbox_lineedit",
            "occurrence": 1,
            "type": "QLineEdit",
            "visible": 1,
            })
        return QLineEdit(self._hid, width_field)

    def get_height_field(self):
        height_field = self._dialog.find_child({
            "name": "qt_spinbox_lineedit",
            "occurrence": 2,
            "type": "QLineEdit",
            "visible": 1,
            })
        return QLineEdit(self._hid, height_field)

    def get_opacity_field(self):
        opacity_field = self._dialog.find_child({
            "name": "qt_spinbox_lineedit",
            "occurrence": 3,
            "type": "QLineEdit",
            "visible": 1,
            })
        return QLineEdit(self._hid, opacity_field)

    def browse_background_default_folder(self, background_folder):
        _logger.info('%r: Browse background default folder', self)
        self._hid.mouse_left_click_on_object(self._get_browse_button())
        self._get_file_field().type_text(str(background_folder))
        # To close a tooltip
        self._get_file_field().click()

    def _get_background_overlay(self):
        return self._dialog.find_child({
            "name": "LayoutBackgroundSettingsWidget",
            "type": "nx::vms::client::desktop::LayoutBackgroundSettingsWidget",
            "visible": 1,
            })

    def get_aspect_ratio_field(self):
        aspect_ratio_field = self._get_background_overlay().find_child({
            "name": "keepAspectRatioCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, aspect_ratio_field)

    def crop_setting_is_enabled(self):
        return self.get_crop_checkbox().is_enabled()

    def get_crop_checkbox(self):
        crop_field = self._get_background_overlay().find_child({
            "name": "cropToMonitorCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, crop_field)

    def save_settings(self):
        _logger.info('%r: Save and close', self)
        ok_button = self._dialog.find_child({
            "text": "OK",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)
        self._dialog.wait_until_closed(5)
        # New background rendering takes time.
        time.sleep(1)

    def wait_until_appears(self) -> 'LayoutSettings':
        self._dialog.wait_until_appears()
        return self


class _LayoutNotFoundError(Exception):
    pass
