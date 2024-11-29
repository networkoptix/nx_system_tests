# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from collections.abc import Collection
from collections.abc import Sequence
from typing import Optional

from gui.desktop_ui.dialogs.camera_selection import CameraSelectionDialog
from gui.desktop_ui.dialogs.users_selection import UsersSelectionDialog
from gui.desktop_ui.event_rules._abstract_event_rules_dialog import AbstractEventRulesDialog
from gui.desktop_ui.event_rules._abstract_event_rules_dialog import ActionNames
from gui.desktop_ui.event_rules._abstract_event_rules_dialog import EventNames
from gui.desktop_ui.media_capturing import ImageCapture
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import Checkbox
from gui.desktop_ui.wrappers import ComboBox
from gui.desktop_ui.wrappers import QCheckableButton
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QmlTable
from gui.desktop_ui.wrappers import _TableRow
from gui.testkit import TestKit
from gui.testkit.hid import HID

_action_names = ActionNames(
    BOOKMARK='Create Bookmark',
    TEXT_OVERLAY='Show Text Overlay',
    HTTP_REQUEST='HTTP(S) Request',
    SHOW_DESKTOP_NOTIFICATION='Show Desktop Notification',
    CAMERA_RECORDING='Camera Recording',
    MOBILE_NOTIFICATION='Send Mobile Notification',
    SEND_EMAIL='Send Email',
    SET_FULLSCREEN='Set to Fullscreen',
    )
_event_names = EventNames(
    MOTION='Motion on Camera',
    GENERIC='Generic Event',
    CAMERA_DISCONNECTION='Camera Disconnected',
    SOFT_TRIGGER='Soft Trigger',
    TRIGGER_MOTION='Motion on Camera',
    TRIGGER_GENERIC='Generic Event',
    TRIGGER_CAMERA_DISCONNECTION='Camera Disconnected',
    TRIGGER_SOFT_TRIGGER='Soft Trigger',
    ANALYTICS_EVENT='Analytics Event',
    )


class QmlEventRulesDialog(AbstractEventRulesDialog):
    """Event rules window for VMS 6.1 and higher."""

    def __init__(self, api: TestKit, hid: HID):
        locator = {
            'type': 'VmsRulesDialog',
            'visible': True,
            }
        self._api = api
        self._widget = Widget(self._api, locator_or_obj=locator)
        self._hid = hid

    @staticmethod
    def event_names() -> 'EventNames':
        return _event_names

    @staticmethod
    def action_names() -> 'ActionNames':
        return _action_names

    def click_add_rule_button(self):
        add_rule_button = self._widget.find_child({
            'type': 'Button',
            'visible': True,
            'text': 'Add Rule',
            })
        self._hid.mouse_left_click_on_object(add_rule_button)

    def click_delete_button(self):
        delete_rule_button = self._widget.find_child({
            'type': "TextButton",
            'text': 'Delete',
            'visible': True,
            })
        self._hid.mouse_left_click_on_object(delete_rule_button)

    def close(self):
        _logger.info('%r: Save and close', self)
        ok_button = self._widget.find_child({
            'type': 'Button',
            'text': 'OK',
            'visible': True,
            })
        self._hid.mouse_left_click_on_object(ok_button)
        self._widget.wait_for_inaccessible(10)

    def click_apply_button(self):
        raise RuntimeError('Apply button does not exist for new Event Rules dialog')

    def get_search_field(self):
        search_field = self._widget.find_child({'id': 'searchField', 'visible': True})
        return QLineEdit(self._hid, search_field)

    def row_cell_images(self, event, action, target) -> Sequence[ImageCapture]:
        row = self.get_row_by_values(event=event, action=action, target=target)
        return row.images()

    def get_row_by_values(
            self, event: str, action: str, target: Optional[str] = None) -> _TableRow:
        kwargs = {'event': event, 'action': action}
        if target is not None:
            kwargs['target'] = target
        table_object = self._widget.find_child({
            'id': 'tableView',
            'visible': True,
            })
        table = QmlTable(
            table_object,
            self._hid,
            ['#', 'icon', 'event', 'source', 'action', 'target', 'comment'],
            )
        return table.find_row(**kwargs)

    def select_rule(self, event: str, action: str):
        _logger.info('%r: Select event: "%s", action "%s"', self, event, action)
        row = self.get_row_by_values(event=event, action=action)
        # Checkboxes do not have row/column property. Find the related and click it.
        leftmost_cell_bounds = row.cell('icon').bounds()
        # TODO: Find more straightforward way to do it.
        self._hid.mouse_left_click(leftmost_cell_bounds.center().left(20))

    def get_add_rule_dialog(self) -> '_QmlRuleDialog':
        self.click_add_rule_button()
        return _QmlRuleDialog(self._api, self._hid)

    def is_accessible(self) -> bool:
        return self._widget.is_accessible()

    def wait_for_accessible(self, timeout_sec: float = 3):
        self._widget.wait_for_accessible(timeout_sec)

    def wait_until_appears(self):
        self.wait_for_accessible(10)
        return self


class _QmlRuleDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        locator = {
            'type': 'nx::vms::client::desktop::rules::EditVmsRuleDialog',
            'visible': True,
            'enabled': True,
            }
        self._widget = Widget(api=self._api, locator_or_obj=locator)

    def save_and_close(self):
        button_widget = self._widget.find_child({'type': 'QPushButton', 'text': 'OK'})
        self._hid.mouse_left_click_on_object(Button(button_widget))
        self._widget.wait_for_inaccessible()

    def _get_event_parameters_widget(self) -> Widget:
        widget = self._widget.find_child({
            'type': 'nx::vms::client::desktop::rules::EventParametersWidget',
            'visible': True,
            })
        return widget

    def _get_action_parameters_widget(self) -> Widget:
        widget = self._widget.find_child({
            'type': 'nx::vms::client::desktop::rules::ActionParametersWidget',
            'visible': True,
            })
        return widget

    def _get_event_picker(self) -> ComboBox:
        locator = {
            'name': 'eventTypeComboBox',
            'type': 'QComboBox',
            'visible': True,
            'enabled': True,
            }
        return ComboBox(self._hid, self._widget.find_child(locator))

    def _get_action_picker(self) -> ComboBox:
        locator = {
            'name': 'actionTypeComboBox',
            'type': 'QComboBox',
            'visible': True,
            'enabled': True,
            }
        return ComboBox(self._hid, self._widget.find_child(locator))

    def _select_event(self, event_name: str):
        _logger.info('%r: Select event "%s"', self, event_name)
        combo_box = self._get_event_picker()
        if combo_box.current_item() == event_name:
            _logger.info('%r: Event "%s" is already activated', self, event_name)
            return
        combo_box.open()
        _scroll_combo_box_to_item(self._hid, combo_box, event_name)
        self._hid.mouse_left_click_on_object(combo_box.get_item(event_name))

    def _select_action(self, action_name: str):
        _logger.info('%r: Select action "%s"', self, action_name)
        combo_box = self._get_action_picker()
        if combo_box.current_item() == action_name:
            _logger.info('%r: Action "%s" is already activated', self, action_name)
            return
        combo_box.open()
        _scroll_combo_box_to_item(self._hid, combo_box, action_name)
        self._hid.mouse_left_click_on_object(combo_box.get_item(action_name))

    def get_motion_event(self) -> '_MotionEvent':
        self._select_event(_event_names.MOTION)
        return _MotionEvent(self._get_event_parameters_widget(), self._hid, self._api)

    def get_generic_event(self) -> '_GenericEvent':
        self._select_event(_event_names.GENERIC)
        return _GenericEvent(self._get_event_parameters_widget(), self._hid)

    def get_soft_trigger_event(self) -> '_SoftTriggerEvent':
        self._select_event(_event_names.SOFT_TRIGGER)
        return _SoftTriggerEvent(self._get_event_parameters_widget(), self._hid, self._api)

    def get_bookmark_action(self) -> '_BookmarkAction':
        self._select_action(_action_names.BOOKMARK)
        return _BookmarkAction(self._get_action_parameters_widget(), self._hid, self._api)

    def get_text_overlay_action(self) -> '_TextOverlayAction':
        self._select_action(_action_names.TEXT_OVERLAY)
        return _TextOverlayAction(self._get_action_parameters_widget(), self._hid, self._api)

    def get_desktop_notification_action(self) -> '_ShowDesktopNotificationAction':
        self._select_action(_action_names.SHOW_DESKTOP_NOTIFICATION)
        return _ShowDesktopNotificationAction(
            self._get_action_parameters_widget(),
            self._hid,
            self._api,
            )

    def get_analytics_event(self) -> '_AnalyticsEvent':
        self._select_event(_event_names.ANALYTICS_EVENT)
        return _AnalyticsEvent(self._get_event_parameters_widget(), self._hid, self._api)


class _BaseEvent:

    def __init__(self, window_widget: Widget, hid: HID):
        self._widget = window_widget
        self._hid = hid


class _MotionEvent(_BaseEvent):

    def __init__(self, widget: Widget, hid: HID, api: TestKit):
        self._api = api
        super().__init__(widget, hid)

    def set_cameras(self, camera_names: Collection[str]):
        _logger.info('%r: Set cameras: %s', self, camera_names)
        container = self._widget.find_child({'name': 'cameraId'})
        button = container.find_child({'type': 'QPushButton'})
        self._hid.mouse_left_click_on_object(button)
        dialog = CameraSelectionDialog(self._api, self._hid)
        dialog.select_cameras(camera_names)
        dialog.save()


class _GenericEvent(_BaseEvent):

    def set_trigger(self, value: str):
        _logger.warning(
            '%r: Dialog does not support trigger options setup. Skip setting up "%s" trigger',
            self, value)
        pass


class _SoftTriggerEvent(_BaseEvent):

    def __init__(self, widget: Widget, hid: HID, api: TestKit):
        self._api = api
        super().__init__(widget, hid)

    def get_software_trigger_name_field(self):
        container = self._widget.find_child({'name': 'triggerName'})
        name_qline = container.find_child({'type': 'QLineEdit'})
        return QLineEdit(self._hid, name_qline)

    def set_users_with_groups(self, user_names: str):
        _logger.info('%r: Set users with groups: %s', self, user_names)
        # TODO: Rework arguments type for both types of the dialog.
        self._hid.mouse_left_click_on_object(self._get_select_users_with_group_button())
        dialog = UsersSelectionDialog(self._api, self._hid)
        dialog.select_groups(*[x.strip() for x in user_names.split(sep=',')])
        dialog.close()

    def set_all_users(self):
        _logger.info('%r: Set all users', self)
        self._hid.mouse_left_click_on_object(self._get_select_users_with_group_button())
        dialog = UsersSelectionDialog(self._api, self._hid)
        dialog.select_all_users()
        dialog.close()

    def _get_select_users_with_group_button(self) -> Button:
        container = self._widget.find_child({'name': 'userId'})
        button_widget = container.find_child({'type': 'QPushButton'})
        return Button(button_widget)


class _AnalyticsEvent(_BaseEvent):

    def __init__(self, widget: Widget, hid: HID, api: TestKit):
        self._api = api
        super().__init__(widget, hid)

    def set_cameras(self, camera_names: Collection[str]):
        _logger.info('%r: Set cameras: %s', self, camera_names)
        container = self._widget.find_child({'name': 'cameraId'})
        button = container.find_child({'type': 'QPushButton'})
        self._hid.mouse_left_click_on_object(button)
        dialog = CameraSelectionDialog(self._api, self._hid)
        dialog.select_cameras(camera_names)
        dialog.save()

    def set_analytics_event_type(self, event_type: str):
        _logger.info("%r: Select analytics event type '%s'", self, event_type)
        locator = {
            'name': 'analyticsEventTypeComboBox',
            'type': 'QnTreeComboBox',
            'visible': True,
            'enabled': True,
            }
        combobox = ComboBox(self._hid, self._widget.find_child(locator))
        if combobox.current_item() == event_type:
            _logger.info("%r: Event type '%s' is already selected", self, event_type)
            return
        combobox.open()
        _scroll_combo_box_to_item(self._hid, combobox, event_type)
        self._hid.mouse_left_click_on_object(combobox.get_item(event_type))


class _BaseAction:

    def __init__(self, widget: Widget, hid: HID):
        self._widget = widget
        self._hid = hid


class _BookmarkAction(_BaseAction):

    def __init__(self, widget: Widget, hid: HID, api: TestKit):
        self._api = api
        super().__init__(widget, hid)

    def set_cameras(self, camera_names: Collection[str]):
        _logger.info('%r: Set cameras: %s', self, camera_names)
        container = self._widget.find_child({'name': 'deviceIds'})
        button = container.find_child({'type': 'QPushButton'})
        self._hid.mouse_left_click_on_object(button)
        dialog = CameraSelectionDialog(self._api, self._hid)
        dialog.select_cameras(camera_names)
        dialog.save()

    def get_fixed_duration_box(self) -> QLineEdit:  # The type should be changed to the QSpinBox.
        # There are 2 spin boxes with the same locators.
        container = self._widget.find_child({'name': 'duration'})
        duration_qline = container.find_child({
            'type': 'QSpinBox',
            'visible': True,
            'enabled': True,
            'occurrence': 1,
            })
        return QLineEdit(self._hid, duration_qline)


class _TextOverlayAction(_BaseAction):

    def __init__(self, widget: Widget, hid: HID, api: TestKit):
        self._api = api
        super().__init__(widget, hid)

    def set_cameras(self, camera_names: Collection[str]):
        _logger.info('%r: Set cameras: %s', self, camera_names)
        container = self._widget.find_child({'name': 'deviceIds'})
        button = container.find_child({'type': 'QPushButton'})
        self._hid.mouse_left_click_on_object(button)
        dialog = CameraSelectionDialog(self._api, self._hid)
        dialog.select_cameras(camera_names)
        dialog.save()

    def get_fixed_duration_box(self) -> QLineEdit:  # The type should be changed to the QSpinBox.
        # There are 2 spin boxes with the same locators.
        container = self._widget.find_child({'name': 'duration'})
        duration_qline = container.find_child({
            'type': 'QSpinBox',
            'occurrence': 1,
            })
        return QLineEdit(self._hid, duration_qline)

    def get_use_source_camera_checkbox(self) -> Checkbox:
        container = self._widget.find_child({'name': 'deviceIds'})
        checkbox = container.find_child({
            'type': 'QCheckBox',
            'text': 'Also show on source camera',
            })
        return Checkbox(self._hid, checkbox)


class _ShowDesktopNotificationAction(_BaseAction):

    def __init__(self, widget: Widget, hid: HID, api: TestKit):
        self._api = api
        super().__init__(widget, hid)

    def get_interval_of_action_checkbox(self):
        container = self._widget.find_child({'name': 'interval'})
        widget = container.find_child({'type': 'nx::vms::client::desktop::SlideSwitch'})
        return QCheckableButton(self._hid, widget)

    def set_all_users(self):
        _logger.info('%r: Set all users', self)
        self._hid.mouse_left_click_on_object(self._get_select_users_with_group_button())
        dialog = UsersSelectionDialog(self._api, self._hid)
        dialog.select_all_users()
        dialog.close()

    def _get_select_users_with_group_button(self) -> Button:
        container = self._widget.find_child({'name': 'users'})
        button_widget = container.find_child({'type': 'QPushButton'})
        return Button(button_widget)


def _scroll_combo_box_to_item(hid: HID, combo_box: ComboBox, item_name: str):
    _logger.info('Scroll to item %s', item_name)
    item = combo_box.get_item(item_name)
    list_view = combo_box.get_list_view({'name': 'qt_scrollarea_viewport', 'visible': True})
    if list_view.bounds().contains_rectangle(item.bounds()):
        _logger.info('%r: Item %s is visible, skip scrolling')
        return
    if item.bounds().top_left().y > list_view.bounds().bottom_left().y:
        scroll_delta = 150
    else:
        scroll_delta = -150
    for _ in range(5):
        hid.mouse_scroll(list_view.bounds().center(), scroll_delta=scroll_delta)
        if list_view.bounds().contains_rectangle(item.bounds()):
            return
        _logger.info('Item %s is hidden. Repeat mouse scroll action', item_name)
        time.sleep(0.1)
    raise RuntimeError(f'Item {item_name!r} is unreachable by scroll')


_logger = logging.getLogger(__name__)
