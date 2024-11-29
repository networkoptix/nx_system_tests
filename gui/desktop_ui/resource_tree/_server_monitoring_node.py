# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
from gui.desktop_ui.resource_tree._tree_node import TreeNode
from gui.testkit import TestKit
from gui.testkit.hid import HID


class ServerMonitoringNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        if 'children' in self._data:
            raise ValueError(f"Unexpected children in server monitoring node: {self._data}")

    @classmethod
    def is_server_monitoring_node(cls, model):
        return model['icon'] == cls._icons.ServerMonitoring.value
