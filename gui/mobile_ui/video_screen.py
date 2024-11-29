# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from collections.abc import Collection

from gui.desktop_ui.screen import ScreenRectangle
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import QLabel
from gui.mobile_ui.bookmarks import BookmarksDialog
from gui.mobile_ui.video_output_widget import VideoOutputWidget
from gui.testkit import TestKit
from gui.testkit.hid import HID


class VideoScreen:

    def __init__(self, api: TestKit, hid: HID):
        self._widget = Widget(api, {
            'name': 'VideoScreen',
            'type': 'QQuickContentItem',
            'visible': True,
            'enabled': True,
            })
        self._hid = hid
        self._api = api

    def wait_for_accessible(self):
        self._widget.wait_for_accessible()

    def get_timeline(self) -> '_Timeline':
        widget = self._widget.find_child({'id': 'timeline', 'visible': True})
        return _Timeline(widget, self._hid)

    def get_video_navigator(self) -> '_PlayBackController':
        widget = self._widget.find_child({'id': 'playbackController', 'visible': True})
        return _PlayBackController(widget, self._hid)

    def get_video_output_widget(self) -> 'VideoOutputWidget':
        widget = self._widget.find_child({
            'id': 'video',
            'type': 'MultiVideoOutput',
            'visible': True,
            })
        return VideoOutputWidget(widget)

    def _open_menu(self) -> '_Menu':
        _logger.info('%r: Open Menu', self)
        menu_button = Widget(self._api, {'id': 'controlsRow', 'visible': True})
        self._hid.mouse_left_click_on_object(menu_button)
        list_view_menu = self._widget.find_child({
            'id': 'contentItem',
            'type': 'QQuickListView',
            'visible': True,
            })
        return _Menu(list_view_menu, self._hid)

    def open_bookmarks_dialog(self) -> BookmarksDialog:
        self._open_menu().open_bookmarks()
        return BookmarksDialog(self._api, self._hid)

    def wait_for_inaccessible(self):
        self._widget.wait_for_inaccessible()

    def activate_soft_trigger(self):
        _logger.info('%r: Activate Soft Trigger button', self)
        button_widget = self.get_soft_trigger_widget()
        self._hid.mouse_left_click_on_object(button_widget)

    def get_soft_trigger_text_label(self) -> QLabel:
        text_field = self._widget.find_child({
            'id': 'textItem',
            'type': 'QQuickText',
            'visible': True,
            })
        return QLabel(text_field)

    def get_menu_option_names(self) -> Collection[str]:
        menu = self._open_menu()
        return menu.get_option_names()

    def close_menu(self):
        _logger.info('%r: Close Menu', self)
        video_widget = self.get_video_output_widget()
        self._hid.mouse_left_click(video_widget.bounds().center())

    def get_soft_trigger_widget(self) -> Widget:
        widget = self._widget.find_child({
            'id': 'currentItem',
            'type': 'IconButton',
            'visible': True,
            'enabled': True,
            })
        return widget


class _Timeline:

    def __init__(self, widget: Widget, hid: HID):
        self._widget = widget
        self._hid = hid

    def is_accessible(self) -> bool:
        return self._widget.is_accessible()


class _PlayBackController:

    def __init__(self, widget: Widget, hid: HID):
        self._widget = widget
        self._hid = hid

    def _get_back_button(self) -> Widget:
        # TODO: Add the id field in the mobile client code.
        button = self._widget.find_child({
            'type': 'PlaybackJumpButton',
            'visible': True,
            'occurrence': 1,
            })
        return button

    def jump_backward(self):
        _logger.info('%r: Jump backward', self)
        button = self._get_back_button()
        self._hid.mouse_left_click_on_object(button)

    def wait_for_accessible(self):
        self._widget.wait_for_accessible()


class _Menu:

    def __init__(self, widget: Widget, hid: HID):
        self._widget = widget
        self._hid = hid

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()

    def _get_menu_item(self, text: str) -> Widget:
        widget = self._widget.find_child({
            'type': 'MenuItem',
            'text': text,
            'visible': True,
            })
        return widget

    def open_bookmarks(self):
        _logger.info('%r: Open Bookmarks Dialog', self)
        self._hid.mouse_left_click_on_object(self._get_menu_item('Bookmarks'))

    def get_option_names(self) -> Collection['str']:
        option_widgets = self._widget.find_children({
            'type': 'MenuItem',
            'visible': True,
            })
        option_names = [item.get_text() for item in option_widgets]
        return option_names


_logger = logging.getLogger(__name__)
