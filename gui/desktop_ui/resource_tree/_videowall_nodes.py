# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time

from gui.desktop_ui.dialogs.attach_to_videowall_dialog import AttachToVideoWallDialog
from gui.desktop_ui.resource_tree._tree_node import TreeNode
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class VideowallNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        self._videowall_screens: dict[str, VideowallScreenNode] = {}
        for child_model in self._data.get('children', []):
            if VideowallScreenNode.is_videowall_screen_node(child_model):
                videowall_screen = VideowallScreenNode(api, hid, obj_iter, child_model)
                self._videowall_screens[videowall_screen.name] = videowall_screen
            else:
                raise ValueError(f"Unexpected child node in videowall node: {child_model}")

    @classmethod
    def is_videowall_node(cls, model):
        return model['icon'] == cls._icons.Videowall.value

    def get_all_screens(self):
        return self._videowall_screens

    def open_display_attaching_dialog(self) -> AttachToVideoWallDialog:
        _logger.info('Open Attach to Video Wall Dialog for video wall %s', self.name)
        self._activate_context_menu_item("Attach to Video Wall...")
        return AttachToVideoWallDialog(self._api, self._hid).wait_until_appears()

    def get_single_screen(self):
        if len(self._videowall_screens) == 1:
            return list(self._videowall_screens.values())[0]
        raise ValueError("Video Wall contains several screens")


class VideowallScreenNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        if 'children' in self._data:
            raise ValueError(
                f"Unexpected children in videowall screen node: {self._data}")

    @classmethod
    def is_videowall_screen_node(cls, model):
        return model['icon'] == cls._icons.VideowallScreen.value

    def open(self):
        _logger.info('Open video wall screen %s by double click', self.name)
        self._double_click()
        time.sleep(1)

    def control_video_wall(self):
        _logger.info('Open Control Video Wall Dialog for screen %s', self.name)
        self._activate_context_menu_item('Control Video Wall')
