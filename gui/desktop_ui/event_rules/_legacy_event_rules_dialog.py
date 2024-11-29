# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from abc import ABCMeta
from abc import abstractmethod
from typing import Collection
from typing import Optional
from typing import Sequence

from gui.desktop_ui.dialogs.camera_selection import CameraSelectionDialog
from gui.desktop_ui.dialogs.users_selection import UsersSelectionDialog
from gui.desktop_ui.event_rules._abstract_event_rules_dialog import AbstractEventRulesDialog
from gui.desktop_ui.event_rules._abstract_event_rules_dialog import ActionNames
from gui.desktop_ui.event_rules._abstract_event_rules_dialog import EventNames
from gui.desktop_ui.media_capturing import ImageCapture
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import Checkbox
from gui.desktop_ui.wrappers import ComboBox
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QTable
from gui.desktop_ui.wrappers import _TableRow
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)

_event_names = EventNames(
    MOTION='Motion on Camera',
    GENERIC='Generic Event',
    CAMERA_DISCONNECTION='Camera Disconnected',
    SOFT_TRIGGER='Soft Trigger',
    TRIGGER_MOTION='On Motion on Camera',
    TRIGGER_GENERIC='On Generic Event',
    TRIGGER_CAMERA_DISCONNECTION='On Camera Disconnected',
    TRIGGER_SOFT_TRIGGER='On Soft Trigger',
    ANALYTICS_EVENT='Analytics Event',
    )
_action_names = ActionNames(
    BOOKMARK='Bookmark',
    TEXT_OVERLAY='Show text overlay',
    HTTP_REQUEST='Do HTTP(S) request',
    SHOW_DESKTOP_NOTIFICATION='Show desktop notification',
    CAMERA_RECORDING='Camera recording',
    MOBILE_NOTIFICATION='Send mobile notification',
    SEND_EMAIL='Send email',
    SET_FULLSCREEN='Set to fullscreen',
    )


class _BaseEvent(metaclass=ABCMeta):

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid

    @classmethod
    @abstractmethod
    def name(cls) -> str:
        pass

    def _get_group_box(self):
        return Widget(self._api, {
            "name": "eventDefinitionGroupBox",
            "type": "QGroupBox",
            "visible": 1,
            })

    def set_cameras(self, cameras: Collection[str]):
        _logger.info('%r: Set cameras: %s', self, cameras)
        camera_selector_button = Button(self._get_group_box().find_child({
            "name": "eventResourcesHolder",
            "type": "QPushButton",
            "visible": 1,
            }))
        self._hid.mouse_left_click_on_object(camera_selector_button)
        camera_selection_dialog = CameraSelectionDialog(self._api, self._hid)
        camera_selection_dialog.select_cameras(cameras)
        camera_selection_dialog.save()

    def set_users_with_groups(self, value: str):
        _logger.info('%r: Set users with groups: %s', self, value)
        button = self._get_group_box().find_child({
            "name": "usersButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(button)
        dialog = UsersSelectionDialog(self._api, self._hid)
        dialog.select_groups(*[x.strip() for x in value.split(sep=',')])
        dialog.close()

    def set_all_users(self):
        _logger.info('%r: Set all users', self)
        button = self._get_group_box().find_child({
            "name": "usersButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(button)
        dialog = UsersSelectionDialog(self._api, self._hid)
        dialog.select_all_users()
        dialog.close()

    def set_trigger(self, value: str):
        combobox = self._get_group_box().find_child({
            "name": "eventStatesComboBox",
            "type": "QComboBox",
            "visible": 1,
            })
        ComboBox(self._hid, combobox).select(value)

    def _get_type_combobox(self):
        combobox = self._get_group_box().find_child({
            "name": "eventTypeComboBox",
            "type": "QComboBox",
            "visible": 1,
            })
        return ComboBox(self._hid, combobox)

    def _wait_for_type(self, timeout_sec: float = 2):
        _logger.info(
            '%r: Wait for event type: %s. Timeout: %s second(s)',
            self, self.name(), timeout_sec)
        start_time = time.monotonic()
        while True:
            if self._get_type_combobox().current_item() == self.name():
                return
            if time.monotonic() - start_time > timeout_sec:
                raise RuntimeError("Event type is not set")
            time.sleep(.5)

    def select_type(self):
        _logger.info('%r: Select type: %s', self, self.name)
        self._get_type_combobox().select(self.name())
        self._wait_for_type()


class _BaseAction(metaclass=ABCMeta):

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid

    @abstractmethod
    def name(self) -> str:
        pass

    def _get_group_box(self):
        return Widget(self._api, {
            "name": "actionDefinitionGroupBox",
            "type": "QGroupBox",
            "visible": 1,
            })

    def set_cameras(self, cameras: Collection[str]):
        _logger.info('%r: Set cameras: %s', self, cameras)
        camera_selector_button = self._get_group_box().find_child({
            "name": "actionResourcesHolder",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(camera_selector_button)
        camera_selection_dialog = CameraSelectionDialog(self._api, self._hid)
        camera_selection_dialog.select_cameras(cameras)
        camera_selection_dialog.save()

    def _get_select_users_button(self):
        button = self._get_group_box().find_child({
            "name": "selectUsersButton",
            "type": "QPushButton",
            "visible": 1,
            })
        return Button(button)

    def set_all_users(self):
        _logger.info('%r: Set All Users', self)
        self._hid.mouse_left_click_on_object(self._get_select_users_button())
        dialog = UsersSelectionDialog(self._api, self._hid)
        dialog.select_all_users()
        dialog.close()

    def _get_type_combobox(self):
        combobox = self._get_group_box().find_child({
            "name": "actionTypeComboBox",
            "type": "QComboBox",
            "visible": 1,
            })
        return ComboBox(self._hid, combobox)

    def _wait_for_type(self, timeout_sec: float = 2):
        _logger.info(
            '%r: Wait for event type: %s. Timeout: %s second(s)',
            self, self.name(), timeout_sec)
        start_time = time.monotonic()
        while True:
            if self._get_type_combobox().current_item() == self.name():
                return
            if time.monotonic() - start_time > timeout_sec:
                raise RuntimeError("Event type is not set")
            time.sleep(.5)

    def select_type(self):
        _logger.info('%r: Select type: %s', self, self.name)
        self._get_type_combobox().select(self.name())
        self._wait_for_type()

    def get_use_source_camera_checkbox(self):
        checkbox = self._get_group_box().find_child({
            "name": "useEventSourceCameraCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, checkbox)


class _MotionEvent(_BaseEvent):

    @classmethod
    def name(cls):
        return _event_names.MOTION


class _GenericEvent(_BaseEvent):

    @classmethod
    def name(cls):
        return _event_names.GENERIC

    @classmethod
    def trigger_text(cls):
        return _event_names.TRIGGER_GENERIC


class _SoftTriggerEvent(_BaseEvent):

    @classmethod
    def name(cls):
        return _event_names.SOFT_TRIGGER

    def get_software_trigger_name_field(self):
        name_qline = self._get_group_box().find_child({
            "name": "triggerIdLineEdit",
            "type": "QLineEdit",
            "visible": 1,
            })
        return QLineEdit(self._hid, name_qline)

    @classmethod
    def trigger_text(cls):
        return _event_names.TRIGGER_SOFT_TRIGGER


class _AnalyticsEvent(_BaseEvent):

    @classmethod
    def name(cls):
        return _event_names.ANALYTICS_EVENT

    def set_cameras(self, cameras: Collection[str]):
        _logger.info('%r: Set cameras: %s', self, cameras)
        camera_selector_button = Button(self._get_group_box().find_child({
            "name": "eventResourcesHolder",
            "type": "QPushButton",
            "visible": 1,
            }))
        self._hid.mouse_left_click_on_object(camera_selector_button)
        camera_selection_dialog = CameraSelectionDialog(self._api, self._hid)
        camera_selection_dialog.select_cameras(cameras)
        camera_selection_dialog.save()

    def set_analytics_event_type(self, event_type: str):
        _logger.info("%r: Select analytics event type '%s'", self, event_type)
        widget = self._get_group_box().find_child({
            "type": "QnTreeComboBox",
            "visible": 1,
            })
        ComboBox(self._hid, widget).select(event_type)


class _BookmarkAction(_BaseAction):

    @classmethod
    def name(cls):
        return _action_names.BOOKMARK

    def get_fixed_duration_box(self):
        duration_qline = self._get_group_box().find_child({
            "name": "durationSpinBox",
            "type": "QSpinBox",
            "visible": 1,
            })
        return QLineEdit(self._hid, duration_qline)


class _TextOverlayAction(_BaseAction):

    @classmethod
    def name(cls):
        return _action_names.TEXT_OVERLAY

    def get_overlay_duration_box(self):
        duration_qline = self._get_group_box().find_child({
            "name": "qt_spinbox_lineedit",
            "type": "QLineEdit",
            "visible": 1,
            })
        return QLineEdit(self._hid, duration_qline)

    def get_display_text_for_checkbox(self):
        return Checkbox(self._hid, Widget(self._api, {
            "name": "fixedDurationCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            }))


class _ShowDesktopNotificationAction(_BaseAction):

    @classmethod
    def name(cls):
        return _action_names.SHOW_DESKTOP_NOTIFICATION

    def get_interval_of_action_checkbox(self):
        checkbox = self._get_group_box().find_child({
            "name": "enabledCheckBox",
            "type": "QCheckBox",
            "visible": 1,
            })
        return Checkbox(self._hid, checkbox)


class LegacyEventRulesDialog(BaseWindow, AbstractEventRulesDialog):
    """Event rules window for VMS 6.0."""

    def __init__(self, api: TestKit, hid: HID):
        super().__init__(api=api, locator_or_obj={
            "name": "BusinessRulesDialog",
            "type": "QnBusinessRulesDialog",
            "visible": 1,
            })
        self._hid = hid

    @staticmethod
    def event_names() -> 'EventNames':
        return _event_names

    @staticmethod
    def action_names() -> 'ActionNames':
        return _action_names

    def click_add_rule_button(self):
        add_rule_button = self.find_child({
            "name": "addRuleButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(add_rule_button)

    def click_delete_button(self):
        delete_rule_button = self.find_child({
            "name": "deleteRuleButton",
            "type": "QPushButton",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(delete_rule_button)

    def close(self):
        _logger.info('%r: Save and close', self)
        ok_button = self.find_child({
            "text": "OK",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,

            })
        self._hid.mouse_left_click_on_object(ok_button)
        self.wait_until_closed(10)

    def click_apply_button(self):
        button = self.find_child({
            "text": "Apply",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(button)

    def get_search_field(self):
        search_field = self.find_child({
            "type": "QLineEdit",
            "unnamed": 1,
            "visible": 1,
            })
        return QLineEdit(self._hid, search_field)

    def row_cell_images(self, event, action, target) -> Sequence[ImageCapture]:
        row = self.get_row_by_values(event=event, action=action, target=target)
        return row.images()

    def get_row_by_values(
            self, event: str, action: str, target: Optional[str] = None) -> _TableRow:
        # Testkit returns text of cell with extra space at the end for event column.
        # Dialog redesign in progress. TODO: Remove workaround after it.
        # https://networkoptix.atlassian.net/browse/VMS-6008
        event = event + ' '
        kwargs = {'event': event, 'action': action}
        if target is not None:
            kwargs['target'] = target
        table_object = self.find_child({
            "name": "tableView",
            "type": "nx::vms::client::desktop::TableView",
            "visible": 1,
            })
        table = QTable(self._hid, table_object, ['#', 'on', 'event', 'source', 'arrow', 'action', 'target', 'interval_of_action'])
        return table.find_row(**kwargs)

    def select_rule(self, event: str, action: str):
        _logger.info('%r: Select event: "%s", action "%s"', self, event, action)
        row = self.get_row_by_values(event=event, action=action)
        # Clicking column 0 can inadvertently disable rule.
        row.cell('on').click()

    def get_add_rule_dialog(self) -> '_RuleDialog':
        self.click_add_rule_button()
        return _RuleDialog(self._api, self._hid)


class _RuleDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid

    def save_and_close(self):
        _logger.info(
            '%r: Rule dialog is a part of the Event Rules dialog and can not be'
            ' closed separately. It is expected. Skip.',
            self)

    def get_motion_event(self) -> '_MotionEvent':
        event = _MotionEvent(self._api, self._hid)
        event.select_type()
        return event

    def get_generic_event(self) -> '_GenericEvent':
        event = _GenericEvent(self._api, self._hid)
        event.select_type()
        return event

    def get_soft_trigger_event(self) -> '_SoftTriggerEvent':
        event = _SoftTriggerEvent(self._api, self._hid)
        event.select_type()
        return event

    def get_bookmark_action(self) -> '_BookmarkAction':
        action = _BookmarkAction(self._api, self._hid)
        action.select_type()
        return action

    def get_text_overlay_action(self) -> '_TextOverlayAction':
        action = _TextOverlayAction(self._api, self._hid)
        action.select_type()
        return action

    def get_desktop_notification_action(self) -> '_ShowDesktopNotificationAction':
        action = _ShowDesktopNotificationAction(self._api, self._hid)
        action.select_type()
        return action

    def get_analytics_event(self) -> '_AnalyticsEvent':
        action = _AnalyticsEvent(self._api, self._hid)
        action.select_type()
        return action
