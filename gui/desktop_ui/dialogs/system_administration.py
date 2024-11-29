# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import time
from collections.abc import Collection
from collections.abc import Mapping
from datetime import datetime
from typing import Any

from gui.desktop_ui.bookmarks_log import BookmarksLog
from gui.desktop_ui.dialogs.connect_to_cloud import CloudAuthConnect
from gui.desktop_ui.dialogs.disconnect_from_cloud import DisconnectFromCloudDialog
from gui.desktop_ui.dialogs.user_management import UserManagementWidget
from gui.desktop_ui.dialogs.user_settings import UserSettingsDialog
from gui.desktop_ui.event_log import AbstractEventLogDialog
from gui.desktop_ui.event_log import get_event_log_dialog
from gui.desktop_ui.event_rules import AbstractEventRulesDialog
from gui.desktop_ui.event_rules import get_event_rules_dialog
from gui.desktop_ui.licenses import LicensesTab
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import Checkbox
from gui.desktop_ui.wrappers import ComboBox
from gui.desktop_ui.wrappers import QLabel
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QTable
from gui.desktop_ui.wrappers import TabWidget
from gui.desktop_ui.wrappers import Widget
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class _SecurityTab:

    def __init__(self, api: TestKit, hid: HID):
        self._overlay = Widget(api, {
            "name": "SecuritySettingsWidget",
            "type": "nx::vms::client::desktop::SecuritySettingsWidget",
            "visible": 1,
            })
        self._hid = hid

    def set_watermark_display(self, value: bool):
        _logger.info('%r: Set watermark display checkbox value to %s', self, value)
        display_watermark_checkbox = self._overlay.find_child({
            "name": "displayWatermarkCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        Checkbox(self._hid, display_watermark_checkbox).set(value)

    def watermark_display_is_enabled(self) -> bool:
        button = self._overlay.find_child({
            "name": "watermarkSettingsButton",
            "type": "QPushButton",
            "visible": 1,
            })
        return button.is_enabled()

    def set_display_servers_for_non_administrators(self, value: bool):
        _logger.info(
            '%r: Set displaying servers for non administrators to %s',
            self, value)
        show_servers_in_tree_checkbox = self._overlay.find_child({
            "name": "showServersInTreeCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        Checkbox(self._hid, show_servers_in_tree_checkbox).set(value)


class _CloudTab:

    def __init__(self, api: TestKit, hid: HID):
        self._overlay = Widget(api, {
            "name": "CloudManagementWidget",
            "type": "QnCloudManagementWidget",
            "visible": 1,
            })
        self._api = api
        self._hid = hid

    def get_connected_account(self) -> str:
        connected_account_label = self._overlay.find_child({
            "name": "accountLabel",
            "type": "QLabel",
            "visible": 1,
            })
        return QLabel(connected_account_label).get_text()

    def is_system_connected(self) -> bool:
        system_connected_label = self._overlay.find_child({
            "name": "linkedHintLabel",
            "type": "QLabel",
            "visible": 1,
            })
        if system_connected_label.is_accessible_timeout(0.5):
            actual_text = QLabel(system_connected_label).get_text()
            return re.compile('This (system|site) is connected to').match(actual_text) is not None
        return False

    def wait_for_disconnected(self):
        # The following timeout is required as the system needs time to 'understand'
        # that it has been disconnected and update NxCloud tab.
        timeout_sec = 20
        started_at = time.monotonic()
        while True:
            if not self.is_system_connected():
                return
            if time.monotonic() - started_at > timeout_sec:
                raise RuntimeError(
                    f"System is still connected to Cloud after {timeout_sec} seconds")
            time.sleep(1)

    def open_cloud_connection_window(self) -> CloudAuthConnect:
        _logger.info('%r: Open Cloud Connection window', self)
        link_button = self._overlay.find_child({
            "name": "linkButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(link_button)
        return CloudAuthConnect(self._api, self._hid)

    def connect_system_to_cloud(
            self,
            email: str,
            password: str,
            current_system_password: str,
            cloud_name: str,
            client_connected_to_cloud: bool = False,
            ):
        if not self.is_system_connected():
            cloud_auth = self.open_cloud_connection_window()
            cloud_auth.wait_for_text(f"Log in to {cloud_name}", timeout=25)
            cloud_auth.connect_system(
                email,
                password,
                current_system_password,
                client_connected_to_cloud,
                )

    def get_disconnect_from_cloud_button(self) -> Button:
        unlink_button = self._overlay.find_child({
            "name": "unlinkButton",
            "visible": 1,
            })
        return Button(unlink_button)

    def open_cloud_disconnection_window(self) -> DisconnectFromCloudDialog:
        _logger.info('%r: Open Cloud Disconnect window', self)
        unlink_button = self.get_disconnect_from_cloud_button()
        self._hid.mouse_left_click_on_object(unlink_button)
        return DisconnectFromCloudDialog(self._api, self._hid)


class _EmailTab:
    """Maintain VMS 5.1 version and higher."""

    def __init__(self, api: TestKit, hid: HID):
        self._overlay = Widget(api, {
            "name": "OutgoingMailSettingsWidget",
            "type": "nx::vms::client::desktop::OutgoingMailSettingsWidget",
            "visible": 1,
            })
        self._hid = hid

    def wait_for_open(self):
        self._overlay.wait_for_accessible(1)

    def is_open(self) -> bool:
        return self._overlay.is_accessible_timeout(1)

    def _get_connection_settings_object(self) -> Widget:
        return self._overlay.find_child({
            "name": "connectionSettingsGroupBox",
            "type": "QGroupBox",
            "visible": 1,
            })

    def _get_email_field(self) -> QLineEdit:
        email_field = self._get_connection_settings_object().find_child({
            "occurrence": 1,
            "type": "QLineEdit",
            "unnamed": 1,
            "visible": 1,
            })
        return QLineEdit(self._hid, email_field)

    def set_email(self, value: str):
        _logger.info('%r: Set email', self, value)
        self._get_email_field().type_text(value)

    def set_smtp_server(self, value: str):
        _logger.info('%r: Set SMTP server', self, value)
        smtp_server_field = self._get_connection_settings_object().find_child({
            "occurrence": 2,
            "type": "QLineEdit",
            "unnamed": 1,
            "visible": 1,
            })
        QLineEdit(self._hid, smtp_server_field).type_text(value)

    def clear_email_field(self):
        _logger.info('%r: Clear email field', self)
        self._get_email_field().clear_field()


class _TimeSynchronizationTab:

    def __init__(self, api: TestKit, hid: HID):
        self._overlay = Widget(api, {
            "name": "TimeSynchronizationWidget",
            "type": "nx::vms::client::desktop::TimeSynchronizationWidget",
            "visible": 1,
            })
        self._hid = hid
        self._columns = [None, 'Server', 'Time Zone', 'Date', 'Server OS Time', 'VMS Time']

    def get_servers_time_table(self) -> QTable:
        table = self._overlay.find_child({
            "name": "serversTable",
            "type": "nx::vms::client::desktop::TableView",
            "visible": 1,
            })
        return QTable(self._hid, table, self._columns)

    def servers_time_table_is_accessible(self) -> bool:
        return self.get_servers_time_table().is_accessible()

    def _get_sync_with_internet_checkbox(self) -> Checkbox:
        sync_with_internet_checkbox = self._overlay.find_child({
            "name": "syncWithInternetCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, sync_with_internet_checkbox)

    def get_sync_with_internet_state(self) -> bool:
        return self._get_sync_with_internet_checkbox().is_checked()

    def _get_vms_time_label(self) -> QLabel:
        vms_time = self._overlay.find_child({
            "name": "timeLabel",
            "type": "QLabel",
            "visible": 1,
            })
        return QLabel(vms_time)

    def is_vms_time_shown(self) -> bool:
        return self._get_vms_time_label().is_accessible()

    def set_sync_with_internet(self, value: bool):
        _logger.info('%r: Set synchronization with internet to %s', self, value)
        self._get_sync_with_internet_checkbox().set(value)

    def get_system_synchronized_with_internet_time(self):
        sync_with_internet_date = self._overlay.find_child({
            "name": "dateLabel",
            "type": "QLabel",
            "visible": 1,
            })
        internet_time = QLabel(sync_with_internet_date).get_text() + ' ' + self._get_vms_time_label().get_text()
        fmt = '%m/%d/%Y %I:%M:%S %p'
        return datetime.strptime(internet_time, fmt)

    def get_data_model(self) -> Collection[Mapping[str, Any]]:
        r = []
        raw_rows = self.get_servers_time_table().json_model['data']
        for raw_row in raw_rows:
            keyed = {
                k: v
                for [k, v] in zip(self._columns, raw_row)
                if k is not None
                }
            r.append(keyed)
        return r

    def get_server_current_time(self, server_name: str, column_name: str):
        model = self.get_data_model()
        for row in model:
            if row['Server'] == server_name:
                date_str = row['Date']
                time_str = row[column_name]
                value = date_str + ' ' + time_str
                return datetime.strptime(value, '%m/%d/%Y %I:%M:%S %p')
        raise RuntimeError(f"Cannot find server {server_name} in {model}")


class _GeneralTab:

    def __init__(self, api: TestKit, hid: HID):
        self._overlay = Widget(api, {
            "container": {
                "name": "QnSystemAdministrationDialog",
                "type": "QnSystemAdministrationDialog",
                "visible": 1,
                "occurrence": 1,
                },
            "name": "GeneralSystemAdministrationWidget",
            "visible": 1,
            })
        self._api = api
        self._hid = hid

    def _get_custom_languages_combobox(self) -> ComboBox:
        custom_languages_combobox = self._overlay.find_child({
            "name": "languageComboBox",
            "type": "QComboBox",
            "visible": 1,
            })
        return ComboBox(self._hid, custom_languages_combobox)

    def _get_button_with_text(self, text: str) -> Button:
        button = self._overlay.find_child({
            "text": text,
            "type": "QPushButton",
            "visible": 1,
            })
        return Button(button)

    def open_event_rules(self):
        _logger.info('%r: Open Event Rules Dialog', self)
        event_rules_button = self._get_button_with_text("Event Rules")
        event_rules_button.wait_for_accessible()
        self._hid.mouse_left_click_on_object(event_rules_button)

    def open_event_log(self):
        _logger.info('%r: Open Event Log Dialog', self)
        event_log_button = self._get_button_with_text("Event Log")
        event_log_button.wait_for_accessible()
        self._hid.mouse_left_click_on_object(event_log_button)

    def open_bookmarks_log(self) -> BookmarksLog:
        _logger.info('%r: Open Bookmarks log Dialog', self)
        bookmarks_button = self._get_button_with_text("Bookmarks")
        bookmarks_button.wait_for_accessible()
        self._hid.mouse_left_click_on_object(bookmarks_button)
        return BookmarksLog(self._api, self._hid)

    def set_autodiscovery(self, value: bool):
        _logger.info('%r: Set autodiscovery to %s', self, value)
        autodiscovery_checkbox = self._overlay.find_child({
            "name": "autoDiscoveryCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        Checkbox(self._hid, autodiscovery_checkbox).set(value)

    def set_custom_language_mobile_checkbox(self, value: bool):
        _logger.info(
            '%r: Set custom language mobile notifications checkbox value to %s',
            self, value)
        custom_language_checkbox = self._overlay.find_child({
            "name": "customNotificationLanguageCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        Checkbox(self._hid, custom_language_checkbox).set(value)

    def get_languages_list(self) -> Collection[str]:
        return self._get_custom_languages_combobox().get_list()

    def get_custom_language_mobile(self) -> str:
        return self._get_custom_languages_combobox().current_item()

    def set_custom_language_mobile(self, value: str):
        _logger.info(
            '%r: Set custom language for mobile notifications to %s',
            self, value)
        self._get_custom_languages_combobox().select(value)


class SystemAdministrationDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "QnSystemAdministrationDialog",
            "type": "QnSystemAdministrationDialog",
            "visible": 1,
            "occurrence": 1,
            })
        self.general_tab = _GeneralTab(api, hid)
        self.users_tab = UserManagementWidget(api, hid)
        self.licenses_tab = LicensesTab(api, hid)
        self.email_tab = _EmailTab(api, hid)
        self.security_tab = _SecurityTab(api, hid)
        self.cloud_tab = _CloudTab(api, hid)
        self.time_synchronization_tab = _TimeSynchronizationTab(api, hid)

    def wait_for_accessible(self):
        self._dialog.wait_for_accessible(10)

    def close(self):
        self._dialog.close()

    def apply_changes(self):
        _logger.info('%r: Apply changes', self)
        button = self._get_button_box().find_child({
            "text": "Apply",
            "unnamed": 1,
            "visible": 1,
            })
        if button.is_accessible():
            self._hid.mouse_left_click_on_object(button)

    def save_and_close(self):
        _logger.info('%r: Save and close', self)
        button = self._get_button_box().find_child({
            "text": "OK",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(button)
        self._dialog.wait_until_closed()

    def open_tab(self, tab_name: str):
        _logger.info('%r: Open tab %s', self, tab_name)
        self._dialog.activate()
        # https://networkoptix.atlassian.net/browse/VMS-16938
        # From 6.0 this tab - 'User Management'
        tab_widget = TabWidget(self._dialog.find_child({
            "name": "tabWidget",
            "type": "QTabWidget",
            "visible": 1,
            "occurrence": 1,
            }))
        if tab_name.title() in ('Users', 'User Management'):
            tab_name = 'Users'
            if tab_widget.has_tab('User Management'):
                tab_name = 'User Management'
        tab = tab_widget.find_tab(tab_name.title())
        self._hid.mouse_left_click_on_object(tab)

    def disable_watermark(self):
        self.open_tab('Security')
        self.security_tab.set_watermark_display(False)
        self.save_and_close()

    def enable_watermark(self):
        self.open_tab('Security')
        self.security_tab.set_watermark_display(True)
        self.save_and_close()

    def get_hwid(self) -> str:
        self.open_tab('Licenses')
        self.licenses_tab.set_activation_tab("Manual Activation")
        hwid = self.licenses_tab.get_hwid()
        self._dialog.close()
        return hwid

    def get_manual_activation_message(self) -> str:
        return self.licenses_tab.get_manual_activation_message().get_text()

    def open_event_rules(self) -> AbstractEventRulesDialog:
        self.open_tab('General')
        self.general_tab.open_event_rules()
        event_rules = get_event_rules_dialog(self._api, self._hid)
        event_rules.wait_for_accessible(10)
        return event_rules

    def open_event_log(self) -> AbstractEventLogDialog:
        self.open_tab('General')
        self.general_tab.open_event_log()
        return get_event_log_dialog(self._api, self._hid)

    def open_user_settings(self, username: str) -> UserSettingsDialog:
        self.open_tab('Users')
        return self.users_tab.open_user_settings(username)

    def _get_button_box(self) -> Widget:
        box = self._dialog.find_child({
            'visible': True,
            'type': 'QDialogButtonBox',
            })
        return box

    def cancel_and_close(self):
        _logger.info('%r: Cancel and close', self)
        button = self._get_button_box().find_child({
            "text": "Cancel",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(button)
        self._dialog.wait_until_closed()
