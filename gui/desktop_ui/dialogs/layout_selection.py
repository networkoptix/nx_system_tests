# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.wrappers import BaseWindow
from gui.desktop_ui.wrappers import QTreeView
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class LayoutSelectionDialog:
    """Appears in event rules and maybe somewhere else."""

    def __init__(self, api: TestKit, hid: HID):
        self._dialog = BaseWindow(api=api, locator_or_obj={
            "name": "MultipleLayoutSelectionDialog",
            "type": "nx::vms::client::desktop::MultipleLayoutSelectionDialog",
            "visible": 1,
            })
        self._hid = hid

    def save(self):
        _logger.info('%r: Save and close', self)
        ok_button = self._dialog.find_child({
            "text": "OK",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(ok_button)
        self._dialog.wait_until_closed()

    def cancel(self):
        _logger.info('%r: Click cancel button', self)
        cancel_button = self._dialog.find_child({
            "text": "Cancel",
            "type": "QPushButton",
            "unnamed": 1,
            "visible": 1,
            })
        self._hid.mouse_left_click_on_object(cancel_button)

    def _get_tree_view(self):
        overlay = self._dialog.find_child({
            "name": "stackedWidget",
            "type": "QStackedWidget",
            "visible": 1,
            })
        tree_view = overlay.find_child({
            "name": "treeView",
            "type": "nx::vms::client::desktop::TreeView",
            "visible": 1,
            })
        return QTreeView(tree_view)

    def select_layouts(self, layouts_names: list):
        _logger.info('%r: Select layouts %s', self, *layouts_names)
        for name in layouts_names:
            self._hid.mouse_left_click(self._get_tree_view().get_item_coordinate(name))

    def list_layout_names(self):
        return self._get_tree_view().item_names()
