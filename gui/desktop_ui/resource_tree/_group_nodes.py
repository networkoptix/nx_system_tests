# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui import testkit
from gui.desktop_ui.messages import MessageBox
from gui.desktop_ui.resource_tree._camera_nodes import CameraNode
from gui.desktop_ui.resource_tree._tree_node import TreeNode
from gui.desktop_ui.resource_tree._webpage_nodes import ProxiedWebPageNode
from gui.desktop_ui.wrappers import QMenu
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class GroupNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        self._group_nodes: dict[str, GroupNode] = {}
        self._camera_nodes: dict[str, CameraNode] = {}
        self._proxied_webpage_nodes: dict[str, ProxiedWebPageNode] = {}
        for child_model in self._data.get('children', []):
            if GroupNode.is_group_node(child_model):
                group = GroupNode(api, hid, obj_iter, child_model)
                self._group_nodes[group.name] = group
                self._group_nodes.update(group.get_all_groups())
                self._camera_nodes.update(group.get_all_cameras())
                self._proxied_webpage_nodes.update(group.get_all_proxied_webpages())
            elif CameraNode.is_camera_node(child_model):
                camera = CameraNode(api, hid, obj_iter, child_model)
                self._camera_nodes[camera.name] = camera
            elif ProxiedWebPageNode.is_proxied_webpage(child_model):
                proxied_webpage = ProxiedWebPageNode(api, hid, obj_iter, child_model)
                self._proxied_webpage_nodes[proxied_webpage.name] = proxied_webpage
            else:
                raise ValueError(f"Unexpected child node in group node: {child_model}")

    @classmethod
    def is_group_node(cls, model):
        return model['icon'] == cls._icons.Group.value

    def has_camera(self, camera):
        return camera in self._camera_nodes

    def has_group(self, group_name):
        return group_name in self._group_nodes

    def get_all_cameras(self):
        return self._camera_nodes

    def get_all_proxied_webpages(self):
        return self._proxied_webpage_nodes

    def get_all_groups(self):
        return self._group_nodes

    def remove(self, use_hotkey=False):
        _logger.info('Remove group %s', self.name)
        if use_hotkey:
            self.select()
            self._hid.keyboard_hotkeys('Delete')
        else:
            self._activate_context_menu_item('Remove Group')
        try:
            delete_button = MessageBox(self._api, self._hid).get_button_with_text('Delete')
            self._hid.mouse_left_click_on_object(delete_button)
        except testkit.ObjectNotFound:
            pass

    def _set_group_name(self, name):
        # New group must be expanded and editable after creation.
        if name:
            self.get_name_editor().type_text(name)
        self._hid.keyboard_hotkeys('Return')
        time.sleep(.5)

    def create_group(self, use_hotkey=False, name=None):
        _logger.info('Create group from group %s', self.name)
        if use_hotkey:
            self.select()
            self._hid.keyboard_hotkeys('Ctrl', 'G')
            self._set_group_name(name)
        else:
            self._activate_context_menu_item('Create Group')
            self._set_group_name(name)

    def is_removing_group_available(self):
        menu = QMenu(self._api, self._hid)
        if menu.is_accessible():
            menu.close()
        self._open_context_menu()
        return menu.get_options()['Remove Group'].enabled
