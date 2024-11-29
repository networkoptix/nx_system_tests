# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.file_settings import FileSettings
from gui.desktop_ui.resource_tree._tree_node import TreeNode
from gui.desktop_ui.scene_items import SceneItem
from gui.desktop_ui.wrappers import QMenu
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class LocalFilesNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self._local_file_nodes: dict[str, LocalFileNode] = {}
        for child_model in self._data.get('children', []):
            if LocalFileNode.is_local_file_node(child_model):
                local_file = LocalFileNode(api, hid, obj_iter, child_model)
                self._local_file_nodes[local_file.name] = local_file
            else:
                raise ValueError(f"Unexpected child node in local files node: {child_model}")

    def get_all_local_files(self):
        return self._local_file_nodes


class LocalFileNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        self._video_item_nodes: dict[str, LocalFileNode] = {}
        for child_model in self._data.get('children', []):
            if LocalFileNode.is_local_video_node(child_model):
                video_item_node = LocalFileNode(api, hid, obj_iter, child_model)
                self._video_item_nodes[video_item_node.name] = video_item_node
            else:
                raise ValueError(f"Unexpected child node in local file node: {child_model}")

    @classmethod
    def is_local_file_node(cls, model):
        return model['icon'] in (
            cls._icons.LocalImage.value,
            cls._icons.LocalVideo.value,
            cls._icons.LocalMultiExportInsecure.value,
            cls._icons.LocalMultiExportProtected.value,
            )

    @classmethod
    def is_local_video_node(cls, model):
        return model['icon'] == cls._icons.LocalVideo.value

    def is_image(self):
        return self._data['icon'] == self._icons.LocalImage.value

    def is_protected_multi_export(self):
        return self._data['icon'] == self._icons.LocalMultiExportProtected.value

    def is_insecure_multi_export(self):
        return self._data['icon'] == self._icons.LocalMultiExportInsecure.value

    def has_video_item(self, item_name):
        return item_name in self._video_item_nodes

    def _open_context_menu(self):
        self.right_click()
        QMenu(self._api, self._hid).wait_for_accessible(10)

    def open(self) -> SceneItem:
        _logger.info('Open scene item %s by double click', self.name)
        self._double_click()
        item = SceneItem(self._api, self._hid, self.name)
        if not self.is_protected_multi_export():
            # Scene item opens with a delay after node double click and exceeds 3 seconds default.
            item.wait_for_accessible(timeout=6)
        return item

    def open_in_new_tab(self) -> SceneItem:
        _logger.info('Open local file %s in new tab', self.name)
        self._open_context_menu()
        menu = QMenu(self._api, self._hid)
        menu_options = menu.get_options()
        option_name = 'Open in'  # VMS 6.1 and higher.
        deprecated_option_name = 'Open in New Tab'  # VMS 6.0.
        if deprecated_option_name in menu_options:
            menu.activate_items(deprecated_option_name)
        else:
            menu.activate_items(option_name, 'New Tab')
        return SceneItem(self._api, self._hid, self.name)

    def open_by_context_menu(self) -> SceneItem:
        _logger.info('Open local file %s by context menu', self.name)
        self._activate_context_menu_item("Open")
        return SceneItem(self._api, self._hid, self.name)

    def save_layout(self):
        _logger.info('Save current layout for local file %s', self.name)
        # If local file is .nov or .exe it supports saving the current layout.
        self._activate_context_menu_item("Save Layout")

    def open_settings(self) -> FileSettings:
        _logger.info('Open settings Dialog for local file %s', self.name)
        self._activate_context_menu_item("File Settings...")
        return FileSettings(self._api, self._hid).wait_until_appears()

    def forget_password(self):
        _logger.info('Forget password for local file %s', self.name)
        self._activate_context_menu_item("Forget password")
