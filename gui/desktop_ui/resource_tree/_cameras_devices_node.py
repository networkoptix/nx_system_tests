# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from gui.desktop_ui.resource_tree._camera_nodes import CameraNode
from gui.desktop_ui.resource_tree._group_nodes import GroupNode
from gui.desktop_ui.resource_tree._tree_node import TreeNode
from gui.desktop_ui.resource_tree._webpage_nodes import ProxiedWebPageNode
from gui.testkit import TestKit
from gui.testkit.hid import HID


class CamerasAndDevicesNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
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
                raise ValueError(
                    f"Unexpected child node in cameras and devices node: {child_model}")

    def get_all_cameras(self):
        return self._camera_nodes

    def get_all_proxied_webpages(self):
        return self._proxied_webpage_nodes

    def get_all_groups(self):
        return self._group_nodes

    def show_servers(self):
        self._activate_context_menu_item('Show Servers')
