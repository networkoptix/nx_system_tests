# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.dialogs.user_settings import UserSettingsDialog
from gui.desktop_ui.resource_tree._tree_node import TreeNode
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class CurrentUserNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']

    def open_user_settings(self) -> UserSettingsDialog:
        _logger.info('Open User Settings Dialog')
        self._activate_context_menu_item("User Settings...")
        dialog = UserSettingsDialog(self._api, self._hid)
        dialog.wait_until_appears()
        return dialog
