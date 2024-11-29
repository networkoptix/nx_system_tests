# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui.desktop_ui.event_rules import get_event_rules_dialog
from gui.desktop_ui.right_panel_widget.bookmarks_tab import _BookmarksTab
from gui.desktop_ui.right_panel_widget.events_tab import _EventsTab
from gui.desktop_ui.right_panel_widget.motion_tab import _MotionTab
from gui.desktop_ui.right_panel_widget.notifications_ribbon import NotificationsRibbon
from gui.desktop_ui.right_panel_widget.objects_tab import _ObjectsTab
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QMenu
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class RightPanelWidget:

    def __init__(self, api: TestKit, hid: HID):
        self._overlay = Widget(api, {
            "type": "nx::vms::client::desktop::CompactTabBar",
            "unnamed": 1,
            "visible": 1,
            })
        self._api = api
        self._hid = hid
        self.events_tab = _EventsTab(api)
        self.motion_tab = _MotionTab(api)
        self.bookmarks_tab = _BookmarksTab(api, hid)
        self.objects_tab = _ObjectsTab(api, hid)
        self.notifications_ribbon = NotificationsRibbon(api, hid)

    def _get_button_by_name(self, name: str):
        button = self._overlay.find_child({
            "text": name.upper(),
            "type": "TabItem",
            })
        return Button(button)

    def has_button(self, name: str) -> bool:
        return self._get_button_by_name(name).is_accessible_timeout(0.5)

    def _open_tab(self, tab_name):
        _logger.info('%r: Open tab "%s"', self.__class__.__name__, tab_name)
        self._hid.mouse_left_click_on_object(self._get_button_by_name(tab_name))
        time.sleep(1)

    def objects_tab_is_accessible(self) -> bool:
        return self._get_button_by_name('objects').is_accessible()

    def open_motion_tab_using_hotkey(self):
        self._hid.keyboard_hotkeys('Alt', 'M')

    def open_notification_tab(self):
        self._open_tab('notifications')

    def open_motion_tab(self):
        self._open_tab('motion')

    def open_bookmarks_tab(self):
        self._open_tab('bookmarks')

    def open_events_tab(self):
        self._open_tab('events')

    def open_event_rules(self):
        self._hid.mouse_right_click_on_object(self._get_button_by_name('events'))
        menu = QMenu(self._api, self._hid)
        menu.wait_for_accessible()
        menu.activate_items('Event Rules...')
        return get_event_rules_dialog(self._api, self._hid)

    def open_objects_tab(self):
        self._open_tab('objects')
