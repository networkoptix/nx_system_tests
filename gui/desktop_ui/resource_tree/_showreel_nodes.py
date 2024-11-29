# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui.desktop_ui.resource_tree._tree_node import TreeNode
from gui.desktop_ui.showreels import Showreel
from gui.desktop_ui.wrappers import QMenu
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class ShowreelsNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self._showreel_nodes = {}
        for child_model in self._data.get('children', []):
            if ShowreelNode.is_showreel_node(child_model):
                showreel = ShowreelNode(api, hid, obj_iter, child_model)
                self._showreel_nodes[showreel.name] = showreel
            else:
                raise ValueError(f"Unexpected child node in showreels node: {child_model}")

    def get_all_showreels(self):
        return self._showreel_nodes

    def create_new_showreel(self) -> Showreel:
        _logger.info('Create new Showreel')
        # The Additional click increases stability.
        self.click()
        self._activate_context_menu_item('Add Showreel...')
        return Showreel(self._api, self._hid)


class ShowreelNode(TreeNode):
    # This class is hashable and comparable to compare two sets of showreel nodes.
    # It is a workaround because we don't know the name, with which the new showreel is created.

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        if 'children' in self._data:
            raise ValueError(f"Unexpected children in showreel node: {self._data}")

    @classmethod
    def is_showreel_node(cls, model):
        return model['icon'] == cls._icons.Showreel.value

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        return self.name == other.name

    def open(self) -> Showreel:
        _logger.info('Open showreel %s by double click')
        self._double_click()
        time.sleep(2)
        return Showreel(self._api, self._hid)

    def set_switch_on_timer(self):
        _logger.info('Set switch on timer for showreel %s', self.name)
        self._open_context_menu()
        QMenu(self._api, self._hid).activate_items('Settings', 'Switch on Timer')

    def start_removing(self):
        _logger.info('Start removing showreel %s', self.name)
        self._activate_context_menu_item('Delete')
