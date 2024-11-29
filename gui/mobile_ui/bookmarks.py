# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.screen import ScreenRectangle
from gui.desktop_ui.widget import Widget
from gui.mobile_ui.video_output_widget import VideoOutputWidget
from gui.testkit import TestKit
from gui.testkit.hid import ClickableObject
from gui.testkit.hid import HID


class BookmarksDialog:

    def __init__(self, api: TestKit, hid: HID):
        self._api = api
        self._hid = hid
        self._widget = Widget(self._api, {
            'name': 'eventSearchScreen',
            'title': 'Bookmarks',
            'visible': True,
            })

    def open_bookmark(self, title: str) -> '_BookmarkPlayer':
        _logger.info('%r: Open Bookmark with title "%s"', self, title)
        bookmark = self._get_bookmark(title)
        self._hid.mouse_left_click_on_object(bookmark)
        return _BookmarkPlayer(self._api, self._hid)

    def _get_bookmark(self, title: str) -> '_BookmarkItem':
        widget = self._widget.find_child({
            'title': title,
            'type': 'EventSearchItem',
            'visible': True,
            })
        return _BookmarkItem(widget)

    def wait_for_inaccessible(self):
        self._widget.wait_for_inaccessible()


class _BookmarkItem(ClickableObject):

    def __init__(self, widget: Widget):
        self._widget = widget

    def bounds(self) -> ScreenRectangle:
        return self._widget.bounds()


class _BookmarkPlayer:

    def __init__(self, api: TestKit, hid: HID):
        self._widget = Widget(api, {
            'name': 'mainStackView',
            'id': 'stackView',
            'visible': True,
            })
        self._hid = hid

    def get_video_output_widget(self) -> 'VideoOutputWidget':
        widget = self._widget.find_child({
            'id': 'multiVideoOutput',
            'type': 'MultiVideoOutput',
            'visible': True,
            })
        return VideoOutputWidget(widget)

    def get_playback_panel(self) -> '_PlaybackPanel':
        widget = self._widget.find_child({'id': 'playbackPanel', 'visible': True})
        return _PlaybackPanel(widget)


class _PlaybackPanel:

    def __init__(self, widget: Widget):
        self._widget = widget

    def wait_for_inaccessible(self):
        self._widget.wait_for_inaccessible()


_logger = logging.getLogger(__name__)
