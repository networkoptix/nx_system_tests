# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
import time

from gui.desktop_ui.right_panel_widget.base_tab import _RightPanelTab
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QMenu
from gui.testkit import ObjectNotFound
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class _BookmarksTab(_RightPanelTab):

    def __init__(self, api: TestKit, hid: HID):
        super().__init__(api, {
            "name": "AbstractSearchWidget",
            "type": "nx::vms::client::desktop::BookmarkSearchWidget",
            "visible": 1,
            })
        self._hid = hid

    def is_open(self):
        return self._ribbon.is_accessible()

    def get_bookmark(self, name, description) -> Widget:
        _logger.info(
            '%r: Looking for bookmark with name "%s", description "%s"',
            self, name, description)
        for tile_loader in self.tile_loaders():
            bookmark_name = self._tile_name(tile_loader)
            bookmark_description = self._tile_description(tile_loader)
            if bookmark_name == name and tile_loader.is_visible() and description == bookmark_description:
                return tile_loader
        raise ObjectNotFound(f'No bookmark {name} with description {description} found')

    def wait_for_bookmark(self, name, description):
        start_time = time.monotonic()
        while True:
            if self.has_bookmark(name, description):
                return
            if time.monotonic() - start_time > 5:
                raise RuntimeError(f'No bookmark {name} with description {description} found')
            time.sleep(.1)

    def has_bookmark(self, name, description) -> bool:
        return self.get_bookmark(name, description).is_accessible_timeout(0.5)

    def _tile_name(self, tile_loader: Widget):
        label = tile_loader.find_child({
            "name": "nameLabel",
            "type": "QLabel",
            "visible": 1,
            })
        # Sometimes label.text returns string-like object with html tags.
        # We extract its content without tags.
        text = re.search(r'(?<=>)([\w\s]+)(?=</)', label.get_text())
        if text is None:
            text = label.get_text()
        else:
            text = text.group(0)
        return text

    def _tile_description(self, tile_loader: Widget):
        """Tile.description.text is html code. Method returns clear string."""
        label = tile_loader.find_child({
            "name": "descriptionLabel",
            "type": "QLabel",
            "visible": 1,
            })
        html_description = label.get_text()
        clean = re.compile(r'<.*?>|{.*?}|\n|p, li|hr |li\.(un)?checked::marker')
        return re.sub(clean, '', html_description).strip()

    def time_filter_value(self):
        time_filter_button = self._ribbon.find_child({
            "name": "timeSelectionButton",
            "type": "nx::vms::client::desktop::SelectableTextButton",
            "visible": 1,
            })
        return Button(time_filter_button).get_text()

    def _get_camera_filter_button(self):
        button = self._ribbon.find_child({
            "name": "cameraSelectionButton",
            "type": "nx::vms::client::desktop::SelectableTextButton",
            "visible": 1,
            })
        return Button(button)

    def camera_filter_value(self):
        return self._get_camera_filter_button().get_text()

    def set_camera_filter(self, value):
        _logger.info('%r: Set camera filter to %s', self, value)
        self._hid.mouse_left_click_on_object(self._get_camera_filter_button())
        QMenu(self._api, self._hid).activate_items(value)
        time.sleep(1)
