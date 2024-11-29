# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import re
from typing import Any
from typing import Mapping

from gui.desktop_ui.resource_tree._node_exception import NodeNotFoundError
from gui.desktop_ui.resource_tree._tree_node import TreeNode
from gui.testkit import TestKit
from gui.testkit.hid import HID


class OtherSitesFolder(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self._other_sites_nodes = {}
        for child_model in self._data['children']:
            if OtherSiteNode.is_other_site_node(child_model):
                site = OtherSiteNode(api, hid, obj_iter, child_model)
                self._other_sites_nodes[site.name] = site
            else:
                raise ValueError(
                    f"Unexpected child node in other Sites folder node: {child_model}",
                    )

    def get_all_other_sites(self) -> Mapping[str, 'OtherSiteNode']:
        return self._other_sites_nodes


class OtherSiteNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        self._external_server_nodes: dict[str, ExternalServer] = {}
        for child_model in self._data.get('children', []):
            if ExternalServer.is_external_server(child_model):
                pending_server = ExternalServer(api, hid, obj_iter, child_model)
                self._external_server_nodes[pending_server.name] = pending_server
            else:
                raise ValueError(f"Unexpected child node in other Sites node: {child_model}")

    @classmethod
    def is_other_site_node(cls, model: Mapping[str, Any]) -> bool:
        return model['icon'] == cls._icons.OtherSystem.value

    def get_external_server(self, external_server_name: str) -> 'ExternalServer':
        if external_server_name in self._external_server_nodes:
            return self._external_server_nodes[external_server_name]
        raise NodeNotFoundError(
            node=f'Group {external_server_name}',
            target=f'server {self.name}',
            )


class ExternalServer(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        if 'children' in self._data:
            raise ValueError(f"Unexpected children in pending server node: {self._data}")

    @classmethod
    def is_external_server(cls, model: Mapping[str, Any]) -> bool:
        return model['icon'] in (
            cls._icons.ServerNotConnected.value,
            cls._icons.Server.value,
            )

    def activate_merge(self):
        _logger.info('Activate merge to currently connected site with %s', self.name)
        self._activate_context_menu_item(re.compile('Merge to Currently Connected (System|Site)...'))


_logger = logging.getLogger(__name__)
