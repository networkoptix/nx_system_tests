# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import builtins
import logging
import time
from typing import Optional

from gui import testkit
from gui.desktop_ui.main_window import get_control_layer
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.right_panel_widget.base_tab import _remove_html_tags
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.widget import WidgetIsNotAccessible
from gui.desktop_ui.wrappers import Button
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class _NotificationTile:

    def __init__(self, obj: Widget, api: TestKit, hid: HID):
        self._qt_tile = obj
        self._api = api
        self._hid = hid

    def get_label_by_name(self, label_name):
        label = self._qt_tile.find_child({
                'name': label_name,
                'type': 'QLabel',
                'visible': 1,
                })
        # TODO: Raise the error if label not accessible. Don't return None. Update related tests.
        if label.is_accessible_timeout(0.5):
            return label

    def exists(self):
        try:
            return self._qt_tile.wait_property('visible')
        except testkit.ObjectAttributeNotFound:
            return False

    def get_name(self):
        name = None
        started_at = time.monotonic()
        label = self.get_label_by_name('nameLabel')
        if label is not None:
            # Sometimes label.text returns string-like object with html tags.
            # We extract its content without tags.
            name = _remove_html_tags(label.get_text())
        _logger.debug(
            "%r: the fetched name is '%s'. Fetching the name took %.2f seconds",
            self, name, time.monotonic() - started_at)
        return name

    def get_html_name(self):
        name = None
        started_at = time.monotonic()
        label = self.get_label_by_name('nameLabel')
        if label is not None:
            name = label.get_text()
        _logger.debug(
            "%r: the fetched name is '%s'. Fetching the name took %.2f seconds",
            self, name, time.monotonic() - started_at)
        return name

    def get_description(self):
        description = None
        started_at = time.monotonic()
        label = self.get_label_by_name('descriptionLabel')
        if label is not None:
            # Text is html, we extract its content without tags.
            description = _remove_html_tags(label.get_text())
        _logger.debug(
            "%r: the fetched description is '%s'. Fetching the description took %.2f seconds",
            self, description, time.monotonic() - started_at)
        return description

    def hover(self):
        # Tooltip and close buttons are visible only when tile is hovered.
        _logger.info('%r: Hover', self)
        self._hid.mouse_move(self._qt_tile.center())

    def close(self):
        # Hover over tile to make close button visible.
        # Ribbon contains invisible separator tile without close button.
        _logger.info('%r: Close', self)
        self.hover()
        button = self._qt_tile.find_child(
            {
                'type': 'nx::vms::client::desktop::CloseButton',
                'name': 'closeButton',
                "visible": 1,
                },
            timeout=1,
            )
        button.wait_for_accessible(1)
        self._hid.mouse_left_click_on_object(button)

    def click_button(self, name):
        _logger.info('%r: Click action button: %s', self, name)
        buttons = self._qt_tile.find_children({
            "name": "actionButton",
            "type": "nx::vms::client::desktop::ActionPushButton",
            "visible": 1,
            })
        for button in buttons:
            button = Button(button)
            if button.get_text() == name:
                self._hid.mouse_left_click_on_object(button)
                break
        else:
            raise RuntimeError(f'Button with name {name} not found')

    def get_resource_name(self) -> Optional[str]:
        resource_name = None
        started_at = time.monotonic()
        label = self.get_label_by_name('resourceListLabel')
        if label is not None:
            resource_name = _remove_html_tags(label.get_text())
        _logger.debug(
            "%r: Fetched resource name is '%s'. Fetching took %.2f seconds",
            self, resource_name, time.monotonic() - started_at)
        return resource_name

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} wrapper for {self._qt_tile!r}>'


class _UploadingNotificationTile(_NotificationTile):

    def get_progress_bar(self):
        try:
            bar = self._qt_tile.find_child(
                {
                    'name': 'progressBar',
                    "type": 'QProgressBar',
                    "visible": '1',
                    },
                timeout=0.5,
                )
        except testkit.ObjectNotFound:
            return None
        else:
            if bar.is_accessible_timeout(0.5):
                return bar
        return None

    def wait_until_percent(self, percent):
        # TODO: Add a delay.
        while self.get_uploading_percent() < percent:
            pass

    def get_uploading_percent(self):
        if self.exists():
            progress = self.get_progress_bar()
            if progress is not None:
                progress_value = progress.get_text().replace('%', '')
                return builtins.int(progress_value)
        return 100

    def wait_upload_stops(self, duration: int = 10):
        _logger.info('%r: Wait for upload stops. Timeout: %s', self, duration)
        start_time = time.monotonic()
        while True:
            if not self.exists():
                return
            if time.monotonic() - start_time > duration:
                raise TimeoutError(f'Not enough timeout for uploading, current value: {duration}')
            time.sleep(1)

    def cancel_uploading(self, close_notification=True):
        _logger.info('%r: Cancel uploading', self)
        self.close()
        if close_notification:
            _logger.info('%r: Close notification', self)
            MessageBox(self._api, self._hid).close_by_button("Stop")


class NotificationsRibbon:

    def __init__(self, api: TestKit, hid: HID):
        self._obj = Widget(api, {
            "type": "nx::vms::client::desktop::EventRibbon",
            "unnamed": 1,
            "visible": 1,
            })
        self._api = api
        self._hid = hid

    def _get_tile_object(self, tile_object):
        # We consider that UploadingTiles are those that have visible progress_bar. However,
        # file export tile has it too. For now there is no need to distinguish one from another.
        if _UploadingNotificationTile(tile_object, self._api, self._hid).get_progress_bar():
            return _UploadingNotificationTile(tile_object, self._api, self._hid)
        return _NotificationTile(tile_object, self._api, self._hid)

    def tiles(self):
        tiles = self._obj.find_children({
            'type': 'nx::vms::client::desktop::EventTile',
            'visible': '1',
            })
        for tile in reversed(tiles):
            started_at = time.monotonic()
            try:
                tile = self._get_tile_object(tile)
            except testkit.ObjectNotFound:
                _logger.warning(
                    "%r: The notification tile '%r' has been disappeared after %.2f seconds",
                    self, tile, time.monotonic() - started_at)
            else:
                _logger.debug(
                    "%r: Notification tile '%r' has been fetched. Fetching the tile took %.2f seconds",
                    self, tile, time.monotonic() - started_at)
                yield tile

    def has_notification(self, name):
        return bool(self.get_tile_by_name(name))

    def wait_for_notification(self, name, timeout_sec: float = 5, resource_name: Optional[str] = None):
        _logger.info(
            "%r: Wait until notification with name '%s' from resource '%s' appears. Timeout %s seconds",
            self, name, resource_name or 'Any resource', timeout_sec)
        start_time = time.monotonic()
        while True:
            tile = self.get_tile_by_name(name, resource_name)
            if tile is not None:
                return tile
            if time.monotonic() - start_time > timeout_sec:
                resource_name = resource_name or 'Any resource'
                raise RuntimeError(
                    f"Notification with name {name!r} for resource {resource_name!r} is not shown")
            time.sleep(1)

    def wait_for_notification_with_description(
            self,
            description: str,
            timeout_sec: float = 5,
            ) -> _NotificationTile:
        _logger.info(
            "%r: Wait until notification with description '%s' appears. Timeout %s seconds",
            self, description, timeout_sec)
        start_time = time.monotonic()
        while True:
            tile = self._get_tile_by_description(description)
            if tile is not None:
                return tile
            if time.monotonic() - start_time > timeout_sec:
                raise RuntimeError("Notification is not shown")
            time.sleep(0.1)

    def wait_for_notification_disappear(self, name, timeout_sec: float = 5):
        _logger.info(
            "%r: Wait until notification with name '%s' disappears. Timeout %s seconds",
            self, name, timeout_sec)
        start_time = time.monotonic()
        while True:
            tile = self.get_tile_by_name(name)
            if tile is None:
                return
            if time.monotonic() - start_time > timeout_sec:
                raise RuntimeError("Notification is shown")
            time.sleep(1)

    def get_uploading_tile(self) -> _UploadingNotificationTile:
        # Returns the highest uploading tile if there are multiple.
        _logger.info('%r: Looking for uploading notification', self)
        for tile in self.tiles():
            if isinstance(tile, _UploadingNotificationTile):
                return tile

    def wait_for_uploading_tile(self, timeout_sec: float = 3):
        _logger.info(
            '%r: Wait for uploading notification appears. Timeout: %s',
            self, timeout_sec)
        start = time.monotonic()
        while True:
            tile = self.get_uploading_tile()
            if tile is not None:
                return tile
            if time.monotonic() - start > timeout_sec:
                raise RuntimeError('Uploading tile is not shown')
            time.sleep(.5)

    def _get_show_button(self):
        button = get_control_layer(self._api).find_child({
            "acceptDrops": "no",
            "enabled": "yes",
            "focusable": "yes",
            "movable": "no",
            "selectable": "no",
            "type": "QnBlinkingImageButtonWidget",
            "visible": "yes",
            })
        return Button(button)

    def show(self):
        _logger.info('%r: Show', self)
        if not self._obj.is_accessible():
            # Ribbon is hidden, show
            self._hid.mouse_left_click_on_object(self._get_show_button())
        self._obj.wait_for_accessible()

    def hide(self):
        _logger.info('%r: Hide', self)
        if self._obj.is_accessible():
            # Ribbon is shown, hide
            self._hid.mouse_left_click_on_object(self._get_show_button())
        self._obj.wait_for_inaccessible()

    def get_tile_by_name(self, name, resource_name: Optional[str] = None):
        _logger.info(
            "%r: Looking for notification with name '%s' for resource '%s'",
            self, name, resource_name or 'Any resource')
        started_at = time.monotonic()
        for tile in self.tiles():
            started_at_one_tile = time.monotonic()
            tile_name = tile.get_name()
            tile_resource_name = tile.get_resource_name() if resource_name is not None else None
            _logger.info(
                "%r: Name of current tile is '%s'. Fetching the name took %.2f seconds",
                self, tile_name, time.monotonic() - started_at_one_tile)
            if tile_name == name and tile_resource_name == resource_name:
                resource_name = resource_name or 'Any resource'
                _logger.info(
                    "%r: Notification named '%s' from resource '%s' has been found. It took %.2f seconds",
                    self, name, resource_name, time.monotonic() - started_at)
                return tile
        _logger.info(
            "%r: Notification named '%s' from resource '%s' has not been found. It took %.2f seconds",
            self, name, resource_name, time.monotonic() - started_at)
        return None  # TODO: It used to be so. Consider exception.

    def _get_tile_by_description(self, description: str):
        _logger.info('%r: Looking for notification with description "%s"', self, description)
        started_at = time.monotonic()
        for tile in self.tiles():
            try:
                current_description = tile.get_description()
            except testkit.ObjectNotFound:
                _logger.debug(
                    "%r: The description of the current tile is not accessible - the tile may "
                    "have disappeared",
                    self)
                continue
            _logger.debug('%r: Description of current tile is "%s"', self, current_description)
            if current_description == description:
                _logger.info(
                    "%r: Notification with description '%s' has been found. It took %.2f seconds",
                    self, description, time.monotonic() - started_at)
                return tile
        _logger.info(
            "%r: Notification with description '%s' has not been found. It took %.2f seconds",
            self, description, time.monotonic() - started_at)
        return None  # TODO: It used to be so. Consider exception.

    def close_all_tiles(self):
        for tile in self.tiles():
            try:
                tile.close()
            except (testkit.ObjectNotFound, WidgetIsNotAccessible):
                _logger.warning("%r: The notification tile '%r' has been disappeared", self, tile)
            else:
                _logger.debug("%r: The notification tile '%r' has been closed", self, tile)

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__} wrapper for {self._obj!r}>'
