# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.event_log import AbstractEventLogDialog
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import ComboBox
from gui.desktop_ui.wrappers import QTable
from gui.testkit import TestKit
from gui.testkit.hid import HID


class LegacyEventLog(AbstractEventLogDialog):
    """VMS 6.0."""

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "EventLogDialog",
            "type": "QnEventLogDialog",
            "visible": 1,
            })
        self._hid = hid

    def get_action_filter(self) -> ComboBox:
        action_filter = self._dialog.find_child({
            "name": "actionComboBox",
            "type": "QComboBox",
            "visible": 1,
            })
        return ComboBox(self._hid, action_filter)

    def get_device_filter(self) -> Button:
        device_filter = self._dialog.find_child({
            "name": "cameraButton",
            "type": "QnSelectDevicesButton",
            "visible": 1,
            })
        return Button(device_filter)

    def get_event_filter(self) -> ComboBox:
        event_filter = self._dialog.find_child({
            "name": "eventComboBox",
            "type": "QnTreeComboBox",
            "visible": 1,
            })
        return ComboBox(self._hid, event_filter)

    def _get_table(self) -> QTable:
        table = self._dialog.find_child({
            "name": "gridEvents",
            "type": "nx::vms::client::desktop::TableView",
            "visible": 1,
            })
        return QTable(self._hid, table, ['date_time', 'event', 'source', 'action', 'target', 'description'])

    def is_ready(self) -> bool:
        return self._get_table().is_accessible_timeout(0.5)

    def has_event_with_action(self, event: str, action: str) -> bool:
        _logger.info('%r: Looking for event: "%s", action "%s"', self, event, action)
        row = self._get_table().get_row_index_by_values(
            event=event,
            action=action,
            )
        return row is not None

    def has_event_with_source_and_action(self, event: str, source: str, action: str) -> bool:
        _logger.info(
            '%r: Looking for event with source: "%s", event "%s", action "%s"',
            self, source, event, action)
        row = self._get_table().get_row_index_by_values(
            event=event,
            source=source,
            action=action,
            )
        return row is not None

    def get_description_of_event_with_action(self, event: str, action: str) -> str:
        row = self._get_table().find_row(
            event=event,
            action=action,
            )
        return row.cell('description').tooltip()

    def activate_source_context_menu(self, source: str, context_menu_option: str):
        _logger.info(
            '%r: Activate source "%s", context menu option "%s"',
            self, source, context_menu_option)
        row = self._get_table().find_row(source=source)
        row.cell('source').context_menu(context_menu_option)

    def wait_until_appears(self) -> 'LegacyEventLog':
        self._dialog.wait_until_appears()
        return self

    def is_accessible(self) -> bool:
        return self._dialog.is_accessible()


_logger = logging.getLogger(__name__)
