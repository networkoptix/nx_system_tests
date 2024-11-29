# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import json
import logging
from typing import Sequence

from gui.desktop_ui.resource_tree._camera_nodes import CameraNode
from gui.desktop_ui.resource_tree._cameras_devices_node import CamerasAndDevicesNode
from gui.desktop_ui.resource_tree._group_nodes import GroupNode
from gui.desktop_ui.resource_tree._layout_nodes import LayoutNode
from gui.desktop_ui.resource_tree._layout_nodes import LayoutsNode
from gui.desktop_ui.resource_tree._local_files_nodes import LocalFileNode
from gui.desktop_ui.resource_tree._local_files_nodes import LocalFilesNode
from gui.desktop_ui.resource_tree._other_sites_node import OtherSiteNode
from gui.desktop_ui.resource_tree._other_sites_node import OtherSitesFolder
from gui.desktop_ui.resource_tree._server_nodes import ServerNode
from gui.desktop_ui.resource_tree._server_nodes import ServersNode
from gui.desktop_ui.resource_tree._showreel_nodes import ShowreelNode
from gui.desktop_ui.resource_tree._showreel_nodes import ShowreelsNode
from gui.desktop_ui.resource_tree._user_roles_nodes import CurrentUserNode
from gui.desktop_ui.resource_tree._videowall_nodes import VideowallNode
from gui.desktop_ui.resource_tree._videowall_nodes import VideowallScreenNode
from gui.desktop_ui.resource_tree._webpage_nodes import IntegrationNode
from gui.desktop_ui.resource_tree._webpage_nodes import IntegrationsNode
from gui.desktop_ui.resource_tree._webpage_nodes import ProxiedIntegrationNode
from gui.desktop_ui.resource_tree._webpage_nodes import ProxiedWebPageNode
from gui.desktop_ui.resource_tree._webpage_nodes import WebPageNode
from gui.desktop_ui.resource_tree._webpage_nodes import WebPagesNode
from gui.desktop_ui.widget import Widget
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class NodeStructure:

    def __init__(self, obj: Widget, api: TestKit, hid: HID):
        self.current_user = None
        self.servers_folder = None
        self.cameras_devices_folder = None
        self.users_folder = None
        self.servers: dict[str, ServerNode] = {}
        self.cameras: dict[str, CameraNode] = {}
        self.layouts: dict[str, LayoutNode] = {}
        self.local_files: dict[str, LocalFileNode] = {}
        self.webpages: dict[str, WebPageNode] = {}
        self.proxied_webpages: dict[str, ProxiedWebPageNode] = {}
        self.integrations: dict[str, IntegrationNode] = {}
        self.proxied_integrations: dict[str, ProxiedIntegrationNode] = {}
        self.showreels: dict[str, ShowreelNode] = {}
        self.videowalls: dict[str, VideowallNode] = {}
        self.videowall_screens: dict[str, VideowallScreenNode] = {}
        self.groups: dict[str, GroupNode] = {}
        self.other_sites_folder: None
        self.other_sites: dict[str, OtherSiteNode] = {}
        model_json = (
            obj.wait_for_object()
            .get_attr('model')
            .get_attr('squishFacade')
            .get_attr('jsonModel'))
        model = json.loads(str(model_json))
        list_view = obj.find_child({
            "id": "listView",
            "type": "ListView",
            "visible": True,
            })
        list_view_obj = list_view.wait_for_object()
        item_count = list_view_obj.get_attr('count')
        items = [list_view_obj.call_method('itemAtIndex', i) for i in range(item_count)]
        raw_nodes: Sequence[Widget] = [
            Widget(api, item) for item in items if item]
        indexed_nodes = []
        for [i, node_obj] in enumerate(raw_nodes):
            bounds = node_obj.bounds()
            indexed_nodes.append((bounds.y, i, node_obj))
        ordered_indexed_nodes = sorted(indexed_nodes)
        _obj_iter = (o for [_, _, o] in ordered_indexed_nodes)
        for model_node in model['tree']:
            if model_node['node_type'] == 'camerasAndDevices':
                self._check_devices_uninitialized()
                self.cameras_devices_folder = CamerasAndDevicesNode(api, hid, _obj_iter, model_node)
                self.cameras.update(self.cameras_devices_folder.get_all_cameras())
                self.groups.update(self.cameras_devices_folder.get_all_groups())
            elif model_node['node_type'] == 'servers':
                self._check_devices_uninitialized()
                self.servers_folder = ServersNode(api, hid, _obj_iter, model_node)
                self.servers = self.servers_folder.get_all_servers()
                for server in self.servers.values():
                    self._add_server_resources(server)
            elif model_node['node_type'] == 'resource':
                if ServerNode.is_server_node(model_node):
                    self._check_devices_uninitialized()
                    server = ServerNode(api, hid, _obj_iter, model_node)
                    self.servers[server.name] = server
                    self._add_server_resources(server)
                elif VideowallNode.is_videowall_node(model_node):
                    videowall = VideowallNode(api, hid, _obj_iter, model_node)
                    self.videowalls[videowall.name] = videowall
                    self.videowall_screens.update(videowall.get_all_screens())
                elif LocalFileNode.is_local_file_node(model_node):
                    local_file = LocalFileNode(api, hid, _obj_iter, model_node)
                    self.local_files[local_file.name] = local_file
            elif model_node['node_type'] == 'currentUser':
                self.current_user = CurrentUserNode(api, hid, _obj_iter, model_node)
            elif model_node['node_type'] == 'layouts':
                self.layouts_folder = LayoutsNode(api, hid, _obj_iter, model_node)
                self.layouts.update(self.layouts_folder.get_all_layouts())
            elif model_node['node_type'] == 'showreels':
                self.showreels_folder = ShowreelsNode(api, hid, _obj_iter, model_node)
                self.showreels.update(self.showreels_folder.get_all_showreels())
            elif model_node['node_type'] == 'webPages':
                self.webpages_folder = WebPagesNode(api, hid, _obj_iter, model_node)
                self.webpages.update(self.webpages_folder.get_all_webpages())
                self.proxied_webpages.update(self.webpages_folder.get_all_proxied_webpages())
            elif model_node['node_type'] == 'integrations':
                self.integrations_folder = IntegrationsNode(api, hid, _obj_iter, model_node)
                self.integrations.update(self.integrations_folder.get_all_integrations())
                self.proxied_integrations.update(self.integrations_folder.get_all_proxied_integrations())
            elif model_node['node_type'] == 'otherSystems':
                self.other_sites_folder = OtherSitesFolder(api, hid, _obj_iter, model_node)
                self.other_sites.update(self.other_sites_folder.get_all_other_sites())
            elif model_node['node_type'] == 'localResources':
                self.local_files_folder = LocalFilesNode(api, hid, _obj_iter, model_node)
                self.local_files.update(self.local_files_folder.get_all_local_files())
            else:
                next(_obj_iter)

    def _check_devices_uninitialized(self) -> None:
        if self.servers_folder is None:
            if self.cameras_devices_folder is None:
                if not self.servers:
                    return
        raise ValueError(
            "There can be either "
            "servers node, "
            "single server node or "
            "cameras and devices node")

    def _add_server_resources(self, server) -> None:
        self.cameras.update(server.get_all_cameras())
        self.groups.update(server.get_all_groups())
