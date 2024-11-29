# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui.desktop_ui.dialogs.advanced_object_search import AdvancedObjectSearchDialog
from gui.desktop_ui.right_panel_widget.base_tab import _RightPanelTab
from gui.desktop_ui.wrappers import Button
from gui.desktop_ui.wrappers import QMenu
from gui.testkit import ObjectNotFound
from gui.testkit.hid import HID
from gui.testkit.testkit import TestKit

_logger = logging.getLogger(__name__)


class _ObjectsTab(_RightPanelTab):

    def __init__(self, api: TestKit, hid: HID):
        super().__init__(api, {
            "name": "AbstractSearchWidget",
            "type": 'nx::vms::client::desktop::AnalyticsSearchWidget',
            "visible": 1,
            })
        self._api = api
        self._hid = hid

    def wait_for_tiles(self):
        start_time = time.monotonic()
        while True:
            if self.tile_loaders():
                return
            elif time.monotonic() - start_time > 10:
                raise ObjectNotFound("No tiles appear in Objects tab")
            time.sleep(.1)

    def has_tiles_within_timeout(self):
        try:
            self.wait_for_tiles()
        except ObjectNotFound:
            return False
        return True

    def open_advanced_object_search_dialog(self):
        advanced_button = self._ribbon.find_child({
            "type": "QPushButton",
            "text": "Advanced...",
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(advanced_button)
        return AdvancedObjectSearchDialog(self._api, self._hid)

    def _get_camera_filter_button(self):
        camera_filter_button = self._ribbon.find_child({
            "name": "cameraSelectionButton",
            "type": "nx::vms::client::desktop::SelectableTextButton",
            "visible": 1,
            })
        return Button(camera_filter_button)

    def camera_filter_value(self):
        return self._get_camera_filter_button().get_text()

    def filter_cameras_on_layout(self):
        _logger.info('%r: Set camera filter to "Cameras on layout', self)
        self._hid.mouse_left_click_on_object(self._get_camera_filter_button())
        QMenu(self._api, self._hid).activate_items('Cameras on layout')
