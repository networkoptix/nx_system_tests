# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
from typing import Optional
from typing import Sequence
from typing import Tuple
from uuid import UUID

from gui.desktop_ui.main_window import MainWindow
from gui.desktop_ui.resource_tree import ResourceTree
from gui.desktop_ui.scene_items import CameraSceneItem
from gui.desktop_ui.scene_items import WebPageSceneItem
from gui.testkit import TestKit
from gui.testkit.hid import HID
from installation import Mediaserver
from installation import WindowsClientInstallation
from installation import connect_from_command_line
from installation import open_layout_from_command_line


def start_desktop_client(testkit_port: int, client_installation) -> TestKit:
    client_unit = ClientUnit(testkit_port, client_installation, [])
    return client_unit.testkit()


def start_desktop_client_connected_to_server(
        server_address_port: tuple[str, int],
        testkit_port: int,
        client_installation,
        server: Mediaserver,
        ) -> TestKit:
    username = server.api.get_credentials().username
    password = server.api.get_credentials().password
    client_unit = start_desktop_client_connected_to_server_as_user(
        server_address_port,
        testkit_port,
        client_installation,
        username,
        password,
        )
    return client_unit.testkit()


def start_desktop_client_with_camera_open(
        server_address_port: tuple[str, int],
        testkit_port: int,
        client_installation,
        server: Mediaserver,
        camera_name,
        layout_name: Optional = 'TestLayout',
        ) -> Tuple[TestKit, CameraSceneItem]:
    camera_id = server.api.get_camera_by_name(camera_name).id
    client_unit = _start_desktop_client_connected_to_server_with_resource_open(
        server_address_port,
        testkit_port,
        client_installation,
        server,
        camera_id,
        layout_name,
        )
    camera_scene_item = CameraSceneItem(client_unit.testkit(), client_unit.hid(), camera_name)
    camera_scene_item.wait_for_accessible()
    return client_unit.testkit(), camera_scene_item


def start_client_with_web_page_open(
        server_address_port: tuple[str, int],
        testkit_port: int,
        client: WindowsClientInstallation,
        server: Mediaserver,
        url: str,
        ) -> Tuple[WebPageSceneItem, TestKit, HID]:
    web_page_id = server.api.add_web_page('Test', url)
    client_unit = _start_desktop_client_connected_to_server_with_resource_open(
        server_address_port, testkit_port, client, server, web_page_id)
    scene_item = WebPageSceneItem(client_unit.testkit(), client_unit.hid(), 'Test')
    return scene_item, client_unit.testkit(), client_unit.hid()


def _start_desktop_client_connected_to_server_with_resource_open(
        server_address_port: tuple[str, int],
        testkit_port: int,
        client_installation,
        server: Mediaserver,
        resource_id: UUID,
        layout_name: Optional = 'TestLayout',
        ) -> 'ClientUnit':
    server.api.add_layout_with_resource(
        layout_name,
        resource_id,
        )
    address, port = server_address_port
    username = server.api.get_credentials().username
    password = server.api.get_credentials().password
    client_unit = ClientUnit(testkit_port, client_installation, [
        *connect_from_command_line(address, port, username, password),
        *open_layout_from_command_line(layout_name),
        ])
    return client_unit


def start_desktop_client_connected_to_server_as_user(
        server_address_port: Tuple[str, int],
        testkit_port: int,
        client_installation,
        username,
        password,
        ) -> 'ClientUnit':
    address, port = server_address_port
    client_unit = ClientUnit(testkit_port, client_installation, [
        *connect_from_command_line(address, port, username, password),
        ])
    ResourceTree(client_unit.testkit(), client_unit.hid()).wait_for_current_user()
    return client_unit


class ClientUnit:
    """Test stand unit related to Client's VM, OS, installation and API.

    The intention is to keep common scenarios that require objects of different
    levels of access (TestKit API, OS and the program installed in it, VM).

    An object of this class can be thought of as an DDD aggregate. But the
    difference is that it does provide access to its constituents.
    """

    def __init__(
            self,
            testkit_port: int,
            client_installation: WindowsClientInstallation,
            command_line: Sequence[str],
            ):
        client_installation.prepare_and_start(command_line)
        self._testkit_api = client_installation.connect_testkit(
            timeout=120, testkit_port=testkit_port)
        self._hid = HID(self._testkit_api)
        # sometimes window in fullscreen mode will open behind windows taskbar
        main_window = self.main_window()
        main_window.activate()
        _logger.debug("Bounds of MainWindow: %r", main_window.bounds())

    def main_window(self):
        return MainWindow(self._testkit_api, self._hid)

    def testkit(self):
        return self._testkit_api

    def hid(self):
        return self._hid


_logger = logging.getLogger(__name__)
