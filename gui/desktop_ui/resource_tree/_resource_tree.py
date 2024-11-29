# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from typing import List

from gui.desktop_ui.left_panel_widget import LeftPanelWidget
from gui.desktop_ui.resource_tree._camera_nodes import CameraNode
from gui.desktop_ui.resource_tree._cameras_devices_node import CamerasAndDevicesNode
from gui.desktop_ui.resource_tree._group_nodes import GroupNode
from gui.desktop_ui.resource_tree._layout_nodes import LayoutNode
from gui.desktop_ui.resource_tree._local_files_nodes import LocalFileNode
from gui.desktop_ui.resource_tree._node_exception import NodeNotFoundError
from gui.desktop_ui.resource_tree._node_structure import NodeStructure
from gui.desktop_ui.resource_tree._other_sites_node import OtherSiteNode
from gui.desktop_ui.resource_tree._server_nodes import ServerNode
from gui.desktop_ui.resource_tree._showreel_nodes import ShowreelNode
from gui.desktop_ui.resource_tree._showreel_nodes import ShowreelsNode
from gui.desktop_ui.resource_tree._tree_node import InconsistentResourceTreeModel
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
from gui.desktop_ui.wrappers import QLineEdit
from gui.testkit import TestKit
from gui.testkit.hid import HID

_logger = logging.getLogger(__name__)


class ResourceTree:
    """C++: ResourceTree.qml.

    Wrapper around resource tree object and root node of a resource tree.
    Provides simple methods to obtain elements from the resource tree.
    Nodes, obtained from the tree will always have up-to-date children.
    """

    def __init__(self, api: TestKit, hid: HID):
        _logger.info("%r: Load", self)
        self._obj = Widget(api, {
            "id": "resourceTree",
            "type": "ResourceTree",
            "unnamed": 1,
            "visible": True,
            })
        self._api = api
        self._hid = hid
        self._obj.wait_for_object().call_method('expandAll')
        # ResourceTree can be unstable, especially in _start_desktop_client functions.
        # Use reload to avoid failures in this and other similar places.
        self.reload()

    def __repr__(self):
        return self.__class__.__name__ + '()'

    def reload(self):
        _logger.info("%r: Reload. If 3 times Resource tree is not ready - break", self)
        failed_attempts = 0
        while True:
            self._obj.wait_for_object().call_method('expandAll')
            time.sleep(1)
            failed_attempts += 1
            try:
                self._nodes = NodeStructure(self._obj, self._api, self._hid)
                break
            except InconsistentResourceTreeModel:
                _logger.info("%r: Not ready yet. Trial %s of 3", self, failed_attempts)
            if failed_attempts >= 3:
                raise RuntimeError("Resource tree not ready after 3 attempts, aborting")

    def _get_search_field(self):
        search_field = LeftPanelWidget(self._api, self._hid)._obj.find_child({
            "echoMode": 0,
            "id": "searchField",
            "type": "SearchField",
            "unnamed": 1,
            "visible": True,
            })
        return QLineEdit(self._hid, search_field)

    def set_search(self, text):
        search_field = self._get_search_field()
        search_field.clear_field()
        if text:
            _logger.info('Search in Resource Tree by text %s', text)
            # Doesn't type without click.
            search_field.click()
            search_field.type_text(text, need_activate=False)
            # Wait for filtration to actually happen.
            time.sleep(1)

    def get_search_field_width(self):
        return self._get_search_field().get_width()

    def get_all_resources_node(self) -> CamerasAndDevicesNode:
        if self._nodes.cameras_devices_folder:
            return self._nodes.cameras_devices_folder
        else:
            raise NodeNotFoundError('Cameras and devices')

    def get_current_user(self) -> CurrentUserNode:
        if self._nodes.current_user is not None:
            return self._nodes.current_user
        raise NodeNotFoundError('Current user')

    def has_current_user(self):
        return self._nodes.current_user is not None

    def get_webpages_node(self) -> WebPagesNode:
        if self._nodes.webpages_folder:
            return self._nodes.webpages_folder
        raise NodeNotFoundError('Webpages')

    def get_integrations_node(self) -> IntegrationsNode:
        if self._nodes.integrations_folder:
            return self._nodes.integrations_folder
        raise NodeNotFoundError('Integrations')

    def get_showreels_node(self) -> ShowreelsNode:
        if self._nodes.showreels_folder:
            return self._nodes.showreels_folder
        raise NodeNotFoundError('Showreels')

    def get_server(self, server_name) -> ServerNode:
        if server_name in self._nodes.servers:
            return self._nodes.servers[server_name]
        raise NodeNotFoundError(server_name)

    def get_camera(self, camera) -> CameraNode:
        if camera in self._nodes.cameras:
            return self._nodes.cameras[camera]
        raise NodeNotFoundError(f'Camera {camera}')

    def get_layout(self, layout_name) -> LayoutNode:
        if layout_name in self._nodes.layouts:
            return self._nodes.layouts[layout_name]
        raise NodeNotFoundError(f'Layout {layout_name}')

    def get_group(self, group_name) -> GroupNode:
        if group_name in self._nodes.groups:
            return self._nodes.groups[group_name]
        raise NodeNotFoundError(f'Group {group_name}')

    def get_local_file(self, local_file_name) -> LocalFileNode:
        if local_file_name in self._nodes.local_files:
            return self._nodes.local_files[local_file_name]
        raise NodeNotFoundError(f'Local file {local_file_name}')

    def get_webpage(self, webpage_name) -> WebPageNode:
        if webpage_name in self._nodes.webpages:
            return self._nodes.webpages[webpage_name]
        raise NodeNotFoundError(f'Webpage {webpage_name}')

    def get_proxied_webpage(self, proxied_webpage_name) -> ProxiedWebPageNode:
        if proxied_webpage_name in self._nodes.proxied_webpages:
            return self._nodes.proxied_webpages[proxied_webpage_name]
        raise NodeNotFoundError(f'Proxied webpage {proxied_webpage_name}')

    def get_integration(self, integration_name) -> IntegrationNode:
        if integration_name in self._nodes.integrations:
            return self._nodes.integrations[integration_name]
        raise NodeNotFoundError(f'Integration {integration_name}')

    def get_proxied_integration(self, integration_name) -> ProxiedIntegrationNode:
        if integration_name in self._nodes.proxied_integrations:
            return self._nodes.proxied_integrations[integration_name]
        raise NodeNotFoundError(f'Proxied integration {integration_name}')

    def get_videowall(self, videowall_name) -> VideowallNode:
        if videowall_name in self._nodes.videowalls:
            return self._nodes.videowalls[videowall_name]
        raise NodeNotFoundError(f'Videowall {videowall_name}')

    def get_videowall_screen(self, videowall_screen_name) -> VideowallScreenNode:
        if videowall_screen_name in self._nodes.videowall_screens:
            return self._nodes.videowall_screens[videowall_screen_name]
        raise NodeNotFoundError(f'Videowall screen {videowall_screen_name}')

    def get_showreel(self, showreel_name) -> ShowreelNode:
        if showreel_name in self._nodes.showreels:
            return self._nodes.showreels[showreel_name]
        raise NodeNotFoundError(f'Showreel {showreel_name}')

    def has_all_resources_node(self):
        return False if self._nodes.cameras_devices_folder is None else True

    def has_integrations_node(self):
        try:
            self._nodes.integrations_folder
        except AttributeError:
            return False
        return True

    def has_server(self, server_name):
        return server_name in self._nodes.servers

    def has_group(self, group_name):
        return group_name in self._nodes.groups

    def has_camera(self, camera):
        return camera in self._nodes.cameras

    def has_cameras(self, cameras):
        for camera in cameras:
            if not self.has_camera(camera):
                return False
        else:
            return True

    def has_layout(self, layout_name):
        return layout_name in self._nodes.layouts

    def has_showreel(self, showreel_name):
        return showreel_name in self._nodes.showreels

    def has_videowall(self, videowall_name):
        return videowall_name in self._nodes.videowalls

    def has_videowall_screen(self, videowall_screen_name):
        return videowall_screen_name in self._nodes.videowall_screens

    def has_webpage(self, webpage_name):
        return webpage_name in self._nodes.webpages

    def has_proxied_webpage(self, proxied_webpage_name):
        return proxied_webpage_name in self._nodes.proxied_webpages

    def has_integration(self, integration_name):
        return integration_name in self._nodes.integrations

    def has_proxied_integration(self, integration_name):
        return integration_name in self._nodes.proxied_integrations

    def has_local_file(self, local_file_name):
        return local_file_name in self._nodes.local_files

    def count_servers(self):
        return len(self._nodes.servers)

    def count_layouts(self):
        return len(self._nodes.layouts)

    def count_showreels(self):
        return len(self._nodes.showreels)

    def count_local_files(self):
        return len(self._nodes.local_files)

    def select_all_showreels(self) -> ShowreelNode:
        _logger.info('%r: Select all showreels', self)
        showreel_nodes_list = [node for node in self._nodes.showreels.values()]
        if not showreel_nodes_list[0].is_selected():
            showreel_nodes_list[0].click()
        for cnode in showreel_nodes_list[1:]:
            if not cnode.is_selected():
                cnode.select()
        return showreel_nodes_list[-1]

    def select_cameras(self, camera_name_list: List) -> CameraNode:
        _logger.info('%r: Select cameras: %s', self, camera_name_list)
        camera_node_list = [self.get_camera(camera_name) for camera_name in camera_name_list]
        if not camera_node_list[0].is_selected():
            camera_node_list[0].click()
        for cnode in camera_node_list[1:]:
            if not cnode.is_selected():
                cnode.select()
        return camera_node_list[-1]

    def select_layouts(self, layout_name_list: List) -> LayoutNode:
        _logger.info('%r: Select layouts: %s', self, layout_name_list)
        layout_node_list = [self.get_layout(layout_name) for layout_name in layout_name_list]
        if not layout_node_list[0].is_selected():
            layout_node_list[0].click()
        for layout_node in layout_node_list[1:]:
            if not layout_node.is_selected():
                layout_node.select()
        return layout_node_list[-1]

    def select_groups(self, group_name_list: List) -> GroupNode:
        _logger.info('%r: Select groups: %s', self, group_name_list)
        group_node_list = [self.get_group(group_name) for group_name in group_name_list]
        if not group_node_list[0].is_selected():
            group_node_list[0].click()
        for group_node in group_node_list[1:]:
            if not group_node.is_selected():
                group_node.select()
        return group_node_list[-1]

    def select_files(self, file_name_list: List) -> LocalFileNode:
        _logger.info('%r: Select files: %s', self, file_name_list)
        file_node_list = [self.get_local_file(file_name) for file_name in file_name_list]
        if not file_node_list[0].is_selected():
            file_node_list[0].click()
        for file_node in file_node_list[1:]:
            if not file_node.is_selected():
                file_node.select()
        return file_node_list[-1]

    def select_proxied_webpages(self, proxied_webpage_name_list: List) -> ProxiedWebPageNode:
        _logger.info(
            '%r: Select proxied webpages: %s',
            self, proxied_webpage_name_list)
        proxied_webpage_node_list = [
            self.get_proxied_webpage(proxied_webpage_name)
            for proxied_webpage_name in proxied_webpage_name_list
            ]
        if not proxied_webpage_node_list[0].is_selected():
            proxied_webpage_node_list[0].click()
        for proxied_webpage_node in proxied_webpage_node_list[1:]:
            if not proxied_webpage_node.is_selected():
                proxied_webpage_node.select()
        return proxied_webpage_node_list[-1]

    def hide_servers(self) -> None:
        _logger.info('%r: Hide servers')
        if self._nodes.servers_folder is None:
            node = list(self._nodes.servers.values())[0]
        else:
            node = self._nodes.servers_folder
        node.hide_servers()

    def show_servers(self) -> None:
        _logger.info('%r: Show servers')
        if self._nodes.cameras_devices_folder is None:
            raise NodeNotFoundError('Resource')
        self._nodes.cameras_devices_folder.show_servers()

    def wait_for_current_user(self, timeout: float = 25):
        _logger.info("%r: Wait for current user", self)
        start_time = time.monotonic()
        while True:
            try:
                if self.has_current_user():
                    return
            except StopIteration:
                _logger.info("%r: Not ready yet", self)
            else:
                _logger.info("%r: No current user yet", self)
            if time.monotonic() - start_time > timeout:
                raise CurrentUserNodeNotFound()
            self.reload()

    def wait_for_server_count(self, expected_count, timeout: float = 2):
        _logger.info("%r: Wait for %d servers", self, expected_count)
        start = time.monotonic()
        while True:
            real_count = self.count_servers()
            if real_count == expected_count:
                break
            if time.monotonic() - start > timeout:
                raise RuntimeError(
                    f'Timed out: Wrong showreels quantity found. '
                    f'Expected {expected_count}, got {real_count}.')
            self.reload()

    def wait_for_camera_on_server(self, server_name, camera_name, timeout: float = 10):
        _logger.info("%r: Wait for %s on %s", self, camera_name, server_name)
        start_time = time.monotonic()
        while True:
            if self.get_server(server_name).has_camera(camera_name):
                break
            if time.monotonic() - start_time > timeout:
                raise RuntimeError(
                    f"Camera {camera_name} not found in resource tree "
                    f"as a child of {server_name}")
            self.reload()

    def wait_for_cameras(self, camera_names, timeout: float = 30):
        _logger.info("%r: Wait for cameras %r", self, camera_names)
        start = time.monotonic()
        while True:
            if self.has_cameras(camera_names):
                break
            if time.monotonic() - start > timeout:
                raise RuntimeError(f'Timed out: {camera_names} not found')
            self.reload()

    def wait_for_any_local_file(self, timeout: float = 30):
        # Reload takes 10 second, so timeout should be greater.
        # Increased to 30 to bypass occasional failures while running parallel.
        _logger.info("%r: Wait for any local file", self)
        start = time.monotonic()
        while True:
            if self.count_local_files() > 0:
                break
            if time.monotonic() - start > timeout:
                raise RuntimeError('No local file found')
            _logger.info("%r: No local file yet", self)
            self.reload()

    def wait_for_local_file(self, file_name):
        # Reload takes 10 second, so timeout should be greater.
        _logger.info("%r: Wait for local file %r", self, file_name)
        start = time.monotonic()
        while True:
            try:
                file_node = self.get_local_file(file_name)
                return file_node
            except NodeNotFoundError:
                _logger.info("%r: No %r yet", self, file_name)
            if time.monotonic() - start > 15:
                raise RuntimeError(
                    f'Timed out: File {file_name} not found in resource tree.')
            self.reload()

    def wait_for_showreels_count(self, expected_count: int, timeout: float = 2):
        _logger.info("%r: Wait for %d showreels", self, expected_count)
        start = time.monotonic()
        while True:
            real_count = self.count_showreels()
            if real_count == expected_count:
                break
            if time.monotonic() - start > timeout:
                raise RuntimeError(
                    f'Timed out: Wrong showreels quantity found. '
                    f'Expected {expected_count}, got {real_count}.')
            self.reload()

    def wait_for_integration_node(self, integration_name):
        _logger.info("%r: Wait for integration %r", self, integration_name)
        start = time.monotonic()
        while True:
            try:
                integration_node = self.get_integration(integration_name)
                return integration_node
            except NodeNotFoundError:
                _logger.info("%r: No %r yet", self, integration_name)
            if time.monotonic() - start > 15:
                raise RuntimeError(
                    f'Timed out: Integration {integration_name} not found in resource tree.')
            self.reload()

    def wait_for_proxied_integration_node(self, integration_name):
        _logger.info("%r: Wait for proxied integration %r", self, integration_name)
        start = time.monotonic()
        while True:
            try:
                proxied_integration_node = self.get_proxied_integration(integration_name)
                return proxied_integration_node
            except NodeNotFoundError:
                _logger.info("%r: No %r yet", self, integration_name)
            if time.monotonic() - start > 15:
                raise RuntimeError(
                    f'Timed out: Proxied integration {integration_name} '
                    'not found in resource tree.')
            self.reload()

    def _get_other_site(self, other_site_name: str) -> OtherSiteNode:
        if other_site_name in self._nodes.other_sites:
            return self._nodes.other_sites[other_site_name]
        raise NodeNotFoundError(f'Other Site {other_site_name}')

    def wait_for_other_site(self, other_site_name: str) -> OtherSiteNode:
        _logger.info("%r: Wait for other System|Site %r", self, other_site_name)
        started_at = time.monotonic()
        while True:
            try:
                return self._get_other_site(other_site_name)
            except NodeNotFoundError:
                _logger.info("%r: No %r yet", self, other_site_name)
            if time.monotonic() - started_at > 60:
                raise RuntimeError(
                    f'Timed out: Other Site {other_site_name} '
                    'not found in resource tree.')
            self.reload()


class CurrentUserNodeNotFound(Exception):
    pass
