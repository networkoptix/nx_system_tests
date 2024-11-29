# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from typing import List

from gui.desktop_ui.resource_tree._camera_nodes import CameraNode
from gui.desktop_ui.resource_tree._local_files_nodes import LocalFileNode
from gui.desktop_ui.resource_tree._node_exception import NodeNotFoundError
from gui.desktop_ui.resource_tree._server_monitoring_node import ServerMonitoringNode
from gui.desktop_ui.resource_tree._tree_node import TreeNode
from gui.desktop_ui.resource_tree._webpage_nodes import ProxiedWebPageNode
from gui.desktop_ui.resource_tree._webpage_nodes import WebPageNode
from gui.desktop_ui.showreels import Showreel
from gui.desktop_ui.wrappers import QMenu
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class LayoutsNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self._layout_nodes = {}
        for child_model in self._data.get('children', []):
            if LayoutNode.is_layout_node(child_model):
                layout = LayoutNode(api, hid, obj_iter, child_model)
                self._layout_nodes[layout.name] = layout
            else:
                raise ValueError(f"Unexpected child node in layouts node: {child_model}")

    def get_all_layouts(self):
        return self._layout_nodes


class LayoutNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        self._camera_nodes: dict[str, CameraNode] = {}
        self._local_file_nodes: dict[str, LocalFileNode] = {}
        self._webpage_nodes: dict[str, WebPageNode] = {}
        self._proxied_webpage_nodes: dict[str, ProxiedWebPageNode] = {}
        self._server_monitoring_nodes: dict[str, ServerMonitoringNode] = {}
        for child_model in self._data.get('children', []):
            if CameraNode.is_camera_node(child_model):
                camera = CameraNode(api, hid, obj_iter, child_model)
                self._camera_nodes[camera.name] = camera
            elif LocalFileNode.is_local_file_node(child_model):
                local_file = LocalFileNode(api, hid, obj_iter, child_model)
                self._local_file_nodes[local_file.name] = local_file
            elif WebPageNode.is_webpage_node(child_model):
                webpage = WebPageNode(api, hid, obj_iter, child_model)
                self._webpage_nodes[webpage.name] = webpage
            elif ProxiedWebPageNode.is_proxied_webpage(child_model):
                proxied_webpage = ProxiedWebPageNode(api, hid, obj_iter, child_model)
                self._proxied_webpage_nodes[proxied_webpage.name] = proxied_webpage
            elif ServerMonitoringNode.is_server_monitoring_node(child_model):
                server_monitoring = ServerMonitoringNode(api, hid, obj_iter, child_model)
                self._server_monitoring_nodes[server_monitoring.name] = server_monitoring
            else:
                raise ValueError(f"Unexpected child node in layout node: {child_model}")

    @classmethod
    def is_layout_node(cls, model):
        return model['icon'] in (
            cls._icons.LayoutNotShared.value,
            cls._icons.LayoutShared.value,
            )

    def get_local_file(self, local_file_name) -> LocalFileNode:
        if local_file_name in self._local_file_nodes:
            return self._local_file_nodes[local_file_name]
        raise NodeNotFoundError(
            node=f'Local file {local_file_name}',
            target=f'layout {self.name}',
            )

    def get_camera(self, camera) -> CameraNode:
        if camera in self._camera_nodes:
            return self._camera_nodes[camera]
        raise NodeNotFoundError(
            node=f'Camera {camera}',
            target=f'layout {self.name}',
            )

    def has_server_monitoring(self, server_name):
        return server_name in self._server_monitoring_nodes

    def has_camera(self, camera):
        return camera in self._camera_nodes

    def get_camera_names(self) -> List[str]:
        return list(self._camera_nodes)

    def count_children(self):
        return len((self._data['children']))

    def open(self):
        _logger.info('Open layout %s by double click', self.name)
        self._double_click()

    def open_in_new_tab(self):
        _logger.info('Open layout %s in new tab')
        self._open_context_menu()
        menu = QMenu(self._api, self._hid)
        menu_options = menu.get_options()
        option_name = 'Open in'  # VMS 6.1 and higher.
        deprecated_option_name = 'Open in New Tab'  # VMS 6.0.
        if deprecated_option_name in menu_options:
            menu.activate_items(deprecated_option_name)
        else:
            menu.activate_items(option_name, 'New Tab')

    def open_in_new_window(self):
        _logger.info('Open layout %s in new window')
        self._activate_context_menu_item('Open in New Window')

    def stop_sharing(self):
        _logger.info('Stop sharing layout %s', self.name)
        self._activate_context_menu_item('Stop Sharing Layout')

    def make_showreel(self) -> Showreel:
        _logger.info('Make showreel from layout %s', self.name)
        self._activate_context_menu_item('Make Showreel')
        return Showreel(self._api, self._hid)

    def is_shared(self):
        return self._data['icon'] == self._icons.LayoutShared.value

    def wait_for_shared(self, timeout: float = 3):
        _logger.info(
            'Wait for layout %s becomes shared. Timeout: %s seconds',
            self.name, timeout)
        start_time = time.monotonic()
        while True:
            if self.is_shared():
                return
            if time.monotonic() - start_time > timeout:
                raise RuntimeError(f"Layout {self.name} is not shared")
            time.sleep(.5)
