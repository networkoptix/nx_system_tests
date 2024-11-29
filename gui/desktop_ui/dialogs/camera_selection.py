# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from typing import Collection

from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import QTreeView
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class CameraSelectionDialog:
    """Appears in bookmarks log filter, event rules and maybe somewhere else.

    Reusable.
    Found in different places, so has no open method - it's on the corresponding classes.
    """

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "CameraSelectionDialog",
            "type": "nx::vms::client::desktop::CameraSelectionDialog",
            "visible": 1,
            })
        self._hid = hid

    def save(self):
        _logger.info('%r: Save and close Camera Selection Dialog', self)
        ok_button = self._dialog.find_child({
            "text": "OK",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)
        self._dialog.wait_until_closed()

    def select_cameras(self, camera_names: Collection[str]):
        _logger.info('%r: Select cameras %s in Camera Selection Dialog', self, camera_names)
        tree_view = QTreeView(self._dialog.find_child({
            "name": "treeView",
            "type": "nx::vms::client::desktop::TreeView",
            "visible": 1,
            }))
        for camera in camera_names:
            self._hid.mouse_left_click(tree_view.get_item_coordinate(camera))
