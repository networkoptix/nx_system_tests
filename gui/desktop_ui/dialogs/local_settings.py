# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from typing import List

from gui.desktop_ui.dialogs.upload import CustomUploadDialog
from gui.desktop_ui.dialogs.upload import UploadDialog
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Checkbox
from gui.desktop_ui.wrappers import ComboBox
from gui.desktop_ui.wrappers import QCheckableButton
from gui.desktop_ui.wrappers import QList
from gui.desktop_ui.wrappers import ScrollBar
from gui.desktop_ui.wrappers import TabWidget
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class LocalSettingsDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "LocalSettingsDialog",
            "type": "QnLocalSettingsDialog",
            "visible": 1,
            "occurrence": 1,
            })
        self._hid = hid
        self.general_tab = _GeneralTab(self._dialog, api, hid)
        self.look_and_feel_tab = _LookAndFeelTab(self._dialog, api, hid)
        self.advanced_tab = _AdvancedTab(self._dialog, api, hid)
        self.notifications_tab = _NotificationsTab(self._dialog, api, hid)

    def click_ok_button(self):
        ok_button = self._dialog.find_child({
            "text": "OK",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)

    def click_german_ok_button(self):
        ok_button = self._dialog.find_child({
            "text": "Ok",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)

    def save(self):
        _logger.info('%r: Save and close', self)
        self.click_ok_button()
        self._dialog.wait_for_inaccessible()

    def activate_tab(self, tab_name):
        _logger.info('%r: Activate tab %s', self, tab_name)
        tab_bar = self._dialog.find_child({
            "name": "qt_tabwidget_tabbar",
            "type": "QTabBar",
            "visible": 1,
            })
        tab = TabWidget(tab_bar).find_tab(tab_name)
        self._hid.mouse_left_click_on_object(tab)

    def add_folder(self, path):
        _logger.info('%r: Add folder %s', self, path)
        if path not in self.general_tab.get_local_media_folders():
            self.general_tab.set_local_media_folders(str(path))
        self.save()

    def wait_until_appears(self):
        self._dialog.wait_until_appears()
        return self


class _BaseTab:

    def __init__(
            self,
            base_dialog: BaseWindow,
            overlay_name: str,
            api: TestKit,
            hid: HID,
            ):
        self._base_dialog = base_dialog
        self._overlay_name = overlay_name
        self._api = api
        self._hid = hid

    def _get_overlay_widget(self):
        return self._base_dialog.find_child({
            "name": f"{self._overlay_name}Widget",
            "type": f"Qn{self._overlay_name}Widget",
            "visible": 1,
            })


class _GeneralTab(_BaseTab):

    def __init__(self, base_dialog: BaseWindow, api: TestKit, hid: HID):
        super().__init__(base_dialog, "GeneralPreferences", api, hid)

    def get_local_media_folders(self) -> List[str]:
        folders_list = self._get_overlay_widget().find_child({
            "name": "mediaFoldersList",
            "type": "QListWidget",
            "visible": 1,
            })
        return QList(folders_list).get_values()

    def set_local_media_folders(self, path: str):
        add_folder_button = self._get_overlay_widget().find_child({
            "name": "addMediaFolderButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(add_folder_button)
        UploadDialog(self._api, self._hid).wait_until_appears().upload_folder(path, time_sleep=0)
        if path not in self.get_local_media_folders():
            raise RuntimeError(f"Path {path} not fount among local media folders")

    def set_restore_session(self, value: bool):
        _logger.info('%r: Set restore session checkbox value to %s', self, value)
        check_box = self._get_overlay_widget().find_child({
            "name": "restoreSessionCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        Checkbox(self._hid, check_box).set(value)


class _LookAndFeelTab(_BaseTab):

    def __init__(self, base_dialog: BaseWindow, api: TestKit, hid: HID):
        super().__init__(base_dialog, "LookAndFeelPreferences", api, hid)

    def _get_locale_box(self):
        language_combo_box = self._get_overlay_widget().find_child({
            "name": "languageComboBox",
            "type": "QComboBox",
            "visible": 1,
            })
        return ComboBox(self._hid, language_combo_box)

    def _get_enabled_background_button(self):
        language_combo_box = self._get_overlay_widget().find_child({
            "name": "imageGroupBox",
            "type": "QGroupBox",
            "visible": 1,
            })
        return QCheckableButton(self._hid, language_combo_box)

    def get_locale(self) -> str:
        return self._get_locale_box().current_item()

    def is_background_checked(self) -> bool:
        return self._get_enabled_background_button().is_checked()

    def set_locale(self, language: str):
        _logger.info('%r: Set locale %s', self, language)
        self._get_locale_box().select(language)

    def set_background_enabled(self, value: bool):
        _logger.info('%r: Set background checkbox value to %s', self, value)
        self._get_enabled_background_button().set_checked(value)

    def set_background_image(self, image_path: str):
        _logger.info('%r: Set background image %s', self, image_path)
        if not self.is_background_checked():
            raise RuntimeError("Background is not checked")
        background_image_button = self._get_overlay_widget().find_child({
            "name": "imageSelectButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(background_image_button)
        CustomUploadDialog(self._api, self._hid).wait_until_appears().upload_file(image_path, 0)

    def open_time_mode_info(self):
        _logger.info('%r: Open time mode info', self)
        time_mode_label = self._get_overlay_widget().find_child({
            "name": "timeModeLabel",
            "type": "QLabel",
            "visible": 1,
            })
        time_mode_button = time_mode_label.find_child({
            "type": "nx::vms::client::desktop::HintButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(time_mode_button)

    def open_additional_info(self):
        _logger.info('%r: Open additional info', self)
        show_info_button = self._get_overlay_widget().find_child({
            "name": "showIpInTreeCheckBoxHint",
            "type": "nx::vms::client::desktop::HintButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(show_info_button)

    def open_tour_cycle_info(self):
        _logger.info('%r: Open tour cycle info', self)
        tour_cycle_label = self._get_overlay_widget().find_child({
            "name": "tourCycleTimeLabel",
            "type": "QLabel",
            "visible": 1,
            })
        tour_cycle_button = tour_cycle_label.find_child({
            "type": "nx::vms::client::desktop::HintButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(tour_cycle_button)


class _AdvancedTab(_BaseTab):

    def __init__(self, base_dialog: BaseWindow, api: TestKit, hid: HID):
        super().__init__(base_dialog, "AdvancedSettings", api, hid)

    def reset_warnings_settings(self):
        _logger.info('%r: Reset warnings settings', self)
        reset_warnings_button = self._get_overlay_widget().find_child({
            "name": "resetAllWarningsButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(reset_warnings_button)


class _NotificationsTab(_BaseTab):

    def __init__(self, base_dialog: BaseWindow, api: TestKit, hid: HID):
        super().__init__(base_dialog, "PopupSettings", api, hid)

    def set_checkbox_by_text(self, text: str, value: bool):
        _logger.info('%r: Set "%s" checkbox value to %s', self, text, value)
        checkbox = self._get_checkbox_by_text(text)
        scroll_area_bounds = self._base_dialog.find_child({'name': 'scrollArea'}).bounds()
        checkbox_bounds = checkbox.bounds()
        if not scroll_area_bounds.contains_rectangle(checkbox_bounds):
            _logger.info('%r: Scroll to "%s" checkbox', self, text)
            [_, diff_y] = checkbox_bounds.bottom_left().diff(scroll_area_bounds.bottom_left())
            self._scroll_to_checkbox_position(diff_y)
        checkbox.set(value)

    def _get_checkbox_by_text(self, text: str) -> Checkbox:
        checkbox = self._get_overlay_widget().find_child({
            'visible': True,
            'type': 'QCheckBox',
            'text': text,
            })
        return Checkbox(self._hid, checkbox)

    def _scroll_to_checkbox_position(self, position: int):
        widget = self._base_dialog.find_child({
            'visible': True,
            'type': 'QScrollBar',
            })
        scroll_bar = ScrollBar(widget)
        scroll_bar.scroll_to_position(scroll_bar.get_current_position() + position)
