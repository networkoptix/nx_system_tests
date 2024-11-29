# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import time
from typing import Tuple

from gui.desktop_ui.dialogs.connect_to_server import first_time_connect
from gui.desktop_ui.main_menu import MainMenu
from gui.desktop_ui.resource_tree import ResourceTree
from gui.testkit import TestKit
from gui.testkit.hid import HID


def _log_in_to_server(api: TestKit, hid: HID, address_port: Tuple[str, int], server):
    address, port = address_port
    # Default method when you just want to log in to server without specifying any parameters.
    MainMenu(api, hid).activate_connect_to_server().connect(
        address,
        server.api.get_credentials().username,
        server.api.get_credentials().password,
        port,
        )
    first_time_connect(api, hid)
    time.sleep(2)
    ResourceTree(api, hid).wait_for_current_user()


def _log_in_using_main_menu(api: TestKit, hid: HID, address_port: Tuple[str, int], user, password):
    address, port = address_port
    MainMenu(api, hid).activate_connect_to_server().connect(
        address,
        user,
        password,
        port,
        )
    first_time_connect(api, hid)
    time.sleep(2)
    assert ResourceTree(api, hid).has_current_user()
