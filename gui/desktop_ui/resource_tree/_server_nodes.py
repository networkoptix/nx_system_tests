# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re

from gui.desktop_ui.dialogs.add_devices import AddDevicesDialog
from gui.desktop_ui.dialogs.camera_list import CameraListDialog
from gui.desktop_ui.dialogs.edit_webpage import EditWebPageDialog
from gui.desktop_ui.dialogs.server_settings import ServerSettingsDialog
from gui.desktop_ui.resource_tree._camera_nodes import CameraNode
from gui.desktop_ui.resource_tree._group_nodes import GroupNode
from gui.desktop_ui.resource_tree._node_exception import NodeNotFoundError
from gui.desktop_ui.resource_tree._tree_node import TreeNode
from gui.desktop_ui.wrappers import QMenu
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class ServersNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self._server_nodes = {}
        for child_model in self._data['children']:
            if ServerNode.is_server_node(child_model):
                server = ServerNode(api, hid, obj_iter, child_model)
                self._server_nodes[server.name] = server
            else:
                raise ValueError(f"Unexpected child node in servers node: {child_model}")

    def get_all_servers(self):
        return self._server_nodes

    def hide_servers(self):
        self._activate_context_menu_item('Show Servers')


class ServerNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        self._camera_nodes: dict[str, CameraNode] = {}
        self._group_nodes: dict[str, GroupNode] = {}
        for child_model in self._data.get('children', []):
            if CameraNode.is_camera_node(child_model):
                camera = CameraNode(api, hid, obj_iter, child_model)
                self._camera_nodes[camera.name] = camera
            elif GroupNode.is_group_node(child_model):
                group = GroupNode(api, hid, obj_iter, child_model)
                self._group_nodes[group.name] = group
                self._group_nodes.update(group.get_all_groups())
                self._camera_nodes.update(group.get_all_cameras())
            else:
                raise ValueError(f"Unexpected child node in server node: {child_model}")

    @classmethod
    def is_server_node(cls, model):
        return model['icon'] in (
            cls._icons.ServerConnected.value,
            cls._icons.ServerOffline.value,
            cls._icons.ServerNotConnected.value,
            )

    def get_group(self, group_name) -> GroupNode:
        if group_name in self._group_nodes:
            return self._group_nodes[group_name]
        raise NodeNotFoundError(
            node=f'Group {group_name}',
            target=f'server {self.name}',
            )

    def has_group(self, group_name):
        return group_name in self._group_nodes

    def has_camera(self, camera):
        return camera in self._camera_nodes

    def get_all_cameras(self):
        return self._camera_nodes

    def get_all_groups(self):
        return self._group_nodes

    def open_add_device_dialog(self):
        _logger.info('Open Add Device Dialog for server %s', self.name)
        self._open_context_menu()
        QMenu(self._api, self._hid).activate_items(re.compile('^(Add|New)$'), 'Device...')
        return AddDevicesDialog(self._api, self._hid)

    def open_cameras_list(self) -> CameraListDialog:
        _logger.info('Open Camera List Dialog for server %s', self.name)
        self._activate_context_menu_item("Cameras List by Server...")
        camera_list = CameraListDialog(self._api, self._hid)
        camera_list.wait_until_appears()
        return camera_list

    def open_monitoring(self):
        _logger.info('Open Server monitoring for server %s', self.name)
        self._activate_context_menu_item("Monitor")

    def open_settings(self) -> ServerSettingsDialog:
        _logger.info('Open Server Settings Dialog for server %s', self.name)
        self._activate_context_menu_item("Server Settings...")
        server_settings = ServerSettingsDialog(self._api, self._hid)
        server_settings.wait_until_appears()
        return server_settings

    def open_add_proxied_webpage_dialog(self) -> EditWebPageDialog:
        _logger.info('Open Proxied Web Page Dialog for server %s', self.name)
        self._open_context_menu()
        QMenu(self._api, self._hid).activate_items('New', 'Proxied Web Page...')
        return EditWebPageDialog(self._api, self._hid).wait_until_appears()

    def connect_to_server(self):
        _logger.info('Connect to server %s from Resource Tree')
        self._activate_context_menu_item("Connect to this Server")

    def hide_servers(self):
        self._activate_context_menu_item('Show Servers')
