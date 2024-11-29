# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging

from gui.desktop_ui.dialogs.edit_webpage import EditIntegration
from gui.desktop_ui.dialogs.edit_webpage import EditWebPageDialog
from gui.desktop_ui.resource_tree._tree_node import TreeNode
from gui.desktop_ui.scene_items import WebPageSceneItem
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class WebPagesNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self._webpage_nodes: dict[str, WebPageNode] = {}
        self._proxied_webpage_nodes: dict[str, ProxiedWebPageNode] = {}
        for child_model in self._data.get('children', []):
            if WebPageNode.is_webpage_node(child_model):
                webpage = WebPageNode(api, hid, obj_iter, child_model)
                self._webpage_nodes[webpage.name] = webpage
            elif ProxiedWebPageNode.is_proxied_webpage(child_model):
                proxied_webpage = ProxiedWebPageNode(api, hid, obj_iter, child_model)
                self._proxied_webpage_nodes[proxied_webpage.name] = proxied_webpage
            else:
                raise ValueError(f"Unexpected child node in webpages node: {child_model}")

    def get_all_webpages(self):
        return self._webpage_nodes

    def get_all_proxied_webpages(self):
        return self._proxied_webpage_nodes

    def open_new_webpage_dialog(self) -> EditWebPageDialog:
        self._activate_context_menu_item('New Web Page...')
        return EditWebPageDialog(self._api, self._hid)


class WebPageNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        if 'children' in self._data:
            raise ValueError(f"Unexpected children in webpage node: {self._data}")

    @classmethod
    def is_webpage_node(cls, model):
        return model['icon'] == cls._icons.WebPage.value

    def open(self) -> WebPageSceneItem:
        _logger.info('Open web page %s by double click', self.name)
        self._double_click()
        item = WebPageSceneItem(self._api, self._hid, self.name)
        # Scene item opens with a delay after node double click and exceeds 3 seconds default.
        item.wait_for_accessible(timeout=6)
        return item

    def open_settings_dialog(self) -> EditWebPageDialog:
        _logger.info('Open Web Page Settings Dialog for web page %s', self.name)
        self._activate_context_menu_item("Web Page Settings...")
        return EditWebPageDialog(self._api, self._hid).wait_until_appears()


class ProxiedWebPageNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        if 'children' in self._data:
            raise ValueError(f"Unexpected children in proxied webpage node: {self._data}")

    @classmethod
    def is_proxied_webpage(cls, model):
        return model['icon'] == cls._icons.ProxiedWebPage.value

    def open_settings_dialog(self) -> EditWebPageDialog:
        _logger.info('Open Web Page Settings for proxied web page %s', self.name)
        self._activate_context_menu_item("Web Page Settings...")
        return EditWebPageDialog(self._api, self._hid).wait_until_appears()

    def start_removing(self):
        _logger.info('Start removing proxied web page %s', self.name)
        self._activate_context_menu_item("Delete")


class IntegrationsNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self._integration_nodes: dict[str, IntegrationNode] = {}
        self._proxied_integration_nodes: dict[str, ProxiedIntegrationNode] = {}
        for child_model in self._data.get('children', []):
            if IntegrationNode.is_integration_node(child_model):
                integration = IntegrationNode(api, hid, obj_iter, child_model)
                self._integration_nodes[integration.name] = integration
            elif ProxiedIntegrationNode.is_proxied_integration_node(child_model):
                proxied_integration = ProxiedIntegrationNode(api, hid, obj_iter, child_model)
                self._proxied_integration_nodes[proxied_integration.name] = proxied_integration
            else:
                raise ValueError(f"Unexpected child node in integrations node: {child_model}")

    def get_all_integrations(self):
        return self._integration_nodes

    def get_all_proxied_integrations(self):
        return self._proxied_integration_nodes


class IntegrationNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        if 'children' in self._data:
            raise ValueError(f"Unexpected children in webpage node: {self._data}")

    @classmethod
    def is_integration_node(cls, model):
        return model['icon'] == cls._icons.Integration.value

    def open_settings_dialog(self) -> EditIntegration:
        _logger.info('Open Integration Settings Dialog for web page %s', self.name)
        self._activate_context_menu_item("Integration Settings...")
        return EditIntegration(self._api, self._hid).wait_until_appears()


class ProxiedIntegrationNode(TreeNode):

    def __init__(self, api: TestKit, hid: HID, obj_iter, model):
        super().__init__(api, hid, obj_iter, model)
        self.name = self._data['name']
        if 'children' in self._data:
            raise ValueError(f"Unexpected children in webpage node: {self._data}")

    @classmethod
    def is_proxied_integration_node(cls, model):
        return model['icon'] == cls._icons.ProxiedIntegration.value

    def open_settings_dialog(self) -> EditIntegration:
        _logger.info('Open Integration Settings Dialog for web page %s', self.name)
        self._activate_context_menu_item("Integration Settings...")
        return EditIntegration(self._api, self._hid).wait_until_appears()

    def start_removing(self):
        _logger.info('Start removing integration %s', self.name)
        self._activate_context_menu_item("Delete")
