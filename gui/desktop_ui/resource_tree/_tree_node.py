# Copyright 2018-present Network Optix, Inc. Licensed under MPL 2.0: www.mozilla.org/MPL/2.0/
import logging
import time
from enum import Enum
from typing import Iterator
from typing import Optional

from gui.desktop_ui import messages
from gui.desktop_ui.scene_items import Scene
from gui.desktop_ui.screen import ScreenPoint
from gui.desktop_ui.widget import Widget
from gui.desktop_ui.wrappers import QLineEdit
from gui.desktop_ui.wrappers import QMenu
from gui.testkit import TestKit
from gui.testkit.hid import ControlModifier
from gui.testkit.hid import HID

_logger = logging.getLogger('squish.' + __name__)


class ResourceIcons(Enum):
    """VMS-6.0."""

    ServerConnected = 'Server|Control'
    ServerOffline = 'Server|Offline'
    ServerNotConnected = 'Server|Online'
    ServerMonitoring = 'HealthMonitor|Online'
    Group = 'LocalResources'
    CameraOnline = 'Camera|Online'
    CameraOffline = 'Camera|Offline'
    CameraRecording = 'Camera'
    VirtualCamera = 'VirtualCamera|Online'
    LayoutNotShared = 'Layout'
    LayoutShared = 'SharedLayout'
    LocalImage = 'Image|Online'
    LocalVideo = 'Media|Online'
    LocalMultiExportInsecure = 'ExportedLayout'
    LocalMultiExportProtected = 'ExportedEncryptedLayout'
    WebPage = 'WebPage'
    ProxiedWebPage = 'WebPageProxied'
    Integration = 'Integration'
    ProxiedIntegration = 'IntegrationProxied'
    Videowall = 'VideoWall|Online'
    VideowallScreen = 'VideoWallItem|Offline'
    Showreel = 'Showreel'
    OtherSystem = 'OtherSystem'
    Server = 'Server'


class InconsistentResourceTreeModel(Exception):
    pass


class TreeNode:
    """C++: TreeView.qml listItem."""

    _icons = ResourceIcons

    def __init__(
            self,
            api: TestKit,
            hid: HID,
            obj_iter: Iterator[Widget],
            data: Optional[dict] = None,
            ):
        try:
            self._object: Widget = next(obj_iter)
        except StopIteration:
            raise InconsistentResourceTreeModel()
        self._api = api
        self._hid = hid
        self._data = data
        self.name = None

    def click(self):
        _logger.debug('Click Resource Tree node %s with name %s', self, self.name)
        self._hid.mouse_left_click_on_object(self._object)

    def ctrl_click(self):
        _logger.debug('Ctrl click Resource Tree node %s with name %s', self, self.name)
        self._hid.mouse_left_click_on_object(self._object, modifier=ControlModifier)

    def right_click(self):
        _logger.debug('Right click Resource Tree node %s with name %s', self, self.name)
        self._hid.mouse_right_click_on_object(self._object)

    def select(self):
        _logger.debug('Select Resource Tree node %s with name %s', self, self.name)
        if not self.is_selected():
            self.ctrl_click()

    def select_single(self):
        _logger.debug('Select Resource Tree node %s with name %s', self, self.name)
        if not self.is_selected():
            self.click()

    def is_selected(self):
        return self._object.wait_property('isSelected')

    def _double_click(self):
        _logger.debug('Double Click Resource Tree node %s with name %s', self, self.name)
        self._hid.mouse_double_click_on_object(self._object)

    def _open_context_menu(self):
        _logger.debug('Open context menu for %s with name %s', self, self.name)
        self.right_click()
        QMenu(self._api, self._hid).wait_for_accessible(10)

    def context_menu_actions(self):
        self._open_context_menu()
        menu = QMenu(self._api, self._hid)
        menu_options = menu.get_options()
        menu.close()
        return menu_options

    def context_submenu_actions(self, submenu_name: str):
        # Activate submenu item
        self._activate_context_menu_item(submenu_name)
        menu = QMenu(self._api, self._hid)
        menu_options = menu.get_submenu_options(submenu_name)
        # Close submenu
        menu.close()
        # Close menu
        menu.close()
        return menu_options

    def _activate_context_menu_item(self, item_name):
        self._open_context_menu()
        QMenu(self._api, self._hid).activate_items(item_name)
        time.sleep(.5)

    def drag_n_drop(self, target: 'TreeNode'):
        _logger.info('Drag and drop %s on %s', self.name, target.name)
        # Drag and drop to a next below located node can be unstable.
        # Finish drag and drop a little below a center of a target node.
        # The opposite cases are stable due of the logic of resource tree.
        self._hid.mouse_native_drag_and_drop(
            self._object.center(),
            target._object.center().down(5),
            steps=500,
            )

    def drag_n_drop_on_scene(self):
        _logger.info('Drag and drop %s on Scene', self.name)
        self._hid.mouse_native_drag_and_drop(
            self._object.center(),
            Scene(self._api, self._hid)._empty_place_coords(),
            )

    def drag_n_drop_at(self, target: ScreenPoint):
        _logger.info('Drag and drop %s on %s', self.name, target)
        self._hid.mouse_native_drag_and_drop(self._object.center(), target)

    def remove(self, use_hotkey=False):
        _logger.info('Remove %s with name %s from Resource Tree', self, self.name)
        self.click()
        if use_hotkey:
            self._hid.keyboard_hotkeys('Delete')
        else:
            self._activate_context_menu_item('Delete')

        # In case when delete confirmation dialog appeared to need to check
        # that this dialog contains the exact object name that we try to remove
        if (msg_box := messages.MessageBox(self._api, self._hid)).is_accessible():
            if msg_box.has_text(self._data.get('name', None)):
                msg_box.close_by_button('Delete')
                return
            msg_box.close_by_button('Cancel')
            raise messages.MessageBoxContentException()

    def get_name_editor(self):
        resource_tree = Widget(self._api, {
            "id": "resourceTree",
            "type": "ResourceTree",
            "unnamed": 1,
            "visible": True,
            })
        name_editor = resource_tree.find_child({
            "echoMode": 0,
            "id": "nameEditor",
            "type": "TextInput",
            "unnamed": 1,
            "visible": True,
            })
        return QLineEdit(self._hid, name_editor)

    def _type_name_and_save(self, new_name: str):
        _logger.info('Rename %s node with name %s to %s', self, self.name, new_name)
        time.sleep(1)
        self.get_name_editor().type_text(new_name, need_activate=False)
        self._hid.keyboard_hotkeys('Return')
        time.sleep(.5)

    def rename_using_hotkey(self, new_name: str):
        self.click()
        self._hid.keyboard_hotkeys('F2')
        self._type_name_and_save(new_name)

    def rename_using_double_click(self, new_name: str):
        self.click()
        # "Slow" double click.
        time.sleep(1)
        self.click()
        self._type_name_and_save(new_name)

    def rename_using_context_menu(self, new_name):
        self.click()
        self._activate_context_menu_item('Rename')
        self._type_name_and_save(new_name)

    def is_renaming_started(self) -> bool:
        return self.get_name_editor().is_accessible_timeout(0.5)
